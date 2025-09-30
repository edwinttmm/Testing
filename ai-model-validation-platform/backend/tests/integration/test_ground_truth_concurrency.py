"""
Concurrency and Race Condition Testing for Ground Truth System
==============================================================

This module provides comprehensive testing for concurrent operations and race
conditions in the ground truth processing system.

Test Coverage:
- Multiple simultaneous video processing
- Database transaction isolation 
- Resource contention handling
- Thread safety validation
- Processing state management
- Deadlock prevention
- Race condition detection

Author: QA Specialist
Date: 2024-09-29
"""

import pytest
import asyncio
import threading
import time
import uuid
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from unittest.mock import patch, Mock
import queue

from sqlalchemy.orm import Session
from sqlalchemy import text

from database import SessionLocal, engine
from models import Video, GroundTruthObject, DetectionEvent, Project
from services.ground_truth_service import GroundTruthService
from services.detection_pipeline_service import DetectionPipeline

class ConcurrencyTestHelper:
    """Helper class for concurrency testing"""
    
    def __init__(self):
        self.results_queue = queue.Queue()
        self.error_queue = queue.Queue()
        self.test_videos = []
        self.test_projects = []
        
    def create_test_video(self, project_id: str, duration: int = 5) -> Video:
        """Create a test video record"""
        video_id = str(uuid.uuid4())
        self.test_videos.append(video_id)
        
        video = Video(
            id=video_id,
            filename=f"concurrency_test_{video_id[:8]}.mp4",
            file_path=f"/tmp/test_{video_id}.mp4",
            file_size=1024000,
            duration=duration,
            fps=30.0,
            resolution="640x480",
            status="uploaded",
            processing_status="pending",
            ground_truth_generated=False,
            project_id=project_id
        )
        
        db = SessionLocal()
        try:
            db.add(video)
            db.commit()
            db.refresh(video)
            return video
        finally:
            db.close()
    
    def create_test_project(self) -> Project:
        """Create a test project"""
        project_id = str(uuid.uuid4())
        self.test_projects.append(project_id)
        
        project = Project(
            id=project_id,
            name=f"Concurrency Test Project {project_id[:8]}",
            description="Project for concurrency testing",
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
            return project
        finally:
            db.close()
    
    def cleanup(self):
        """Clean up test data"""
        db = SessionLocal()
        try:
            # Clean up videos and related data
            for video_id in self.test_videos:
                db.query(GroundTruthObject).filter(
                    GroundTruthObject.video_id == video_id
                ).delete()
                db.query(DetectionEvent).filter(
                    DetectionEvent.video_id == video_id
                ).delete()
                db.query(Video).filter(Video.id == video_id).delete()
            
            # Clean up projects
            for project_id in self.test_projects:
                db.query(Project).filter(Project.id == project_id).delete()
            
            db.commit()
        except Exception as e:
            print(f"Cleanup warning: {e}")
            db.rollback()
        finally:
            db.close()

@pytest.fixture
def concurrency_helper():
    """Provide concurrency test helper with cleanup"""
    helper = ConcurrencyTestHelper()
    yield helper
    helper.cleanup()

class TestConcurrentVideoProcessing:
    """Test concurrent video processing scenarios"""
    
    @pytest.mark.asyncio
    async def test_multiple_video_processing_async(self, concurrency_helper):
        """Test processing multiple videos concurrently using async"""
        # Arrange
        project = concurrency_helper.create_test_project()
        video_count = 5
        videos = []
        
        for i in range(video_count):
            video = concurrency_helper.create_test_video(project.id)
            videos.append(video)
        
        service = GroundTruthService()
        
        # Act - Process all videos concurrently
        async def process_single_video(video):
            try:
                # Mock the actual processing to avoid ML dependencies
                with patch.object(service, '_extract_detections') as mock_extract:
                    mock_extract.return_value = [
                        {
                            "frame_number": 30,
                            "timestamp": 1.0,
                            "class_label": "pedestrian",
                            "x": 100.0,
                            "y": 200.0,
                            "width": 80.0,
                            "height": 160.0,
                            "confidence": 0.85,
                            "validated": True,
                            "difficult": False
                        }
                    ]
                    
                    await service.process_video_async(video.id, video.file_path)
                    return {"video_id": video.id, "status": "success"}
            except Exception as e:
                return {"video_id": video.id, "status": "error", "error": str(e)}
        
        # Execute concurrent processing
        tasks = [process_single_video(video) for video in videos]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assert - All should complete successfully
        success_count = 0
        for result in results:
            if isinstance(result, dict) and result.get("status") == "success":
                success_count += 1
            elif isinstance(result, Exception):
                print(f"Task failed with exception: {result}")
        
        assert success_count == video_count, f"Expected {video_count} successes, got {success_count}"
        
        # Verify database state
        db = SessionLocal()
        try:
            for video in videos:
                updated_video = db.query(Video).filter(Video.id == video.id).first()
                assert updated_video.ground_truth_generated is True
                assert updated_video.status in ["validated", "completed"]
        finally:
            db.close()
    
    def test_multiple_video_processing_threads(self, concurrency_helper):
        """Test processing multiple videos concurrently using threads"""
        # Arrange
        project = concurrency_helper.create_test_project()
        video_count = 4
        videos = []
        
        for i in range(video_count):
            video = concurrency_helper.create_test_video(project.id)
            videos.append(video)
        
        def process_video_thread(video):
            """Process video in thread"""
            try:
                service = GroundTruthService()
                
                # Mock processing to avoid ML dependencies
                with patch.object(service, '_extract_detections') as mock_extract:
                    mock_extract.return_value = [
                        {
                            "frame_number": 45,
                            "timestamp": 1.5,
                            "class_label": "cyclist",
                            "x": 150.0,
                            "y": 180.0,
                            "width": 90.0,
                            "height": 170.0,
                            "confidence": 0.92,
                            "validated": True,
                            "difficult": False
                        }
                    ]
                    
                    service._process_video(video.id, video.file_path)
                    return {"video_id": video.id, "status": "success"}
            except Exception as e:
                return {"video_id": video.id, "status": "error", "error": str(e)}
        
        # Act - Process using thread pool
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_video = {
                executor.submit(process_video_thread, video): video 
                for video in videos
            }
            
            for future in as_completed(future_to_video):
                video = future_to_video[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "video_id": video.id, 
                        "status": "error", 
                        "error": str(e)
                    })
        
        # Assert - All should complete successfully
        success_count = sum(1 for r in results if r.get("status") == "success")
        assert success_count == video_count, f"Expected {video_count} successes, got {success_count}"

class TestDatabaseConcurrency:
    """Test database concurrency and transaction isolation"""
    
    def test_concurrent_ground_truth_creation(self, concurrency_helper):
        """Test concurrent creation of ground truth objects"""
        # Arrange
        project = concurrency_helper.create_test_project()
        video = concurrency_helper.create_test_video(project.id)
        
        def create_ground_truth_object(index):
            """Create ground truth object in separate thread"""
            try:
                db = SessionLocal()
                try:
                    gt_object = GroundTruthObject(
                        id=str(uuid.uuid4()),
                        video_id=video.id,
                        frame_number=100 + index,
                        timestamp=1.0 + index * 0.1,
                        class_label="pedestrian",
                        x=100.0 + index * 10,
                        y=200.0,
                        width=80.0,
                        height=160.0,
                        confidence=0.8 + index * 0.01,
                        validated=True,
                        difficult=False
                    )
                    
                    db.add(gt_object)
                    db.commit()
                    return {"index": index, "status": "success", "id": gt_object.id}
                finally:
                    db.close()
            except Exception as e:
                return {"index": index, "status": "error", "error": str(e)}
        
        # Act - Create objects concurrently
        thread_count = 10
        results = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(create_ground_truth_object, i) 
                for i in range(thread_count)
            ]
            
            for future in as_completed(futures):
                results.append(future.result())
        
        # Assert - All should succeed
        success_count = sum(1 for r in results if r.get("status") == "success")
        assert success_count == thread_count, f"Expected {thread_count} successes, got {success_count}"
        
        # Verify all objects were created
        db = SessionLocal()
        try:
            gt_count = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).count()
            assert gt_count == thread_count
        finally:
            db.close()
    
    def test_transaction_isolation(self, concurrency_helper):
        """Test transaction isolation between concurrent operations"""
        # Arrange
        project = concurrency_helper.create_test_project()
        video = concurrency_helper.create_test_video(project.id)
        
        isolation_test_results = []
        
        def transaction_test(thread_id):
            """Test transaction isolation"""
            try:
                db = SessionLocal()
                try:
                    # Start transaction
                    db.begin()
                    
                    # Read initial count
                    initial_count = db.query(GroundTruthObject).filter(
                        GroundTruthObject.video_id == video.id
                    ).count()
                    
                    # Add object
                    gt_object = GroundTruthObject(
                        id=str(uuid.uuid4()),
                        video_id=video.id,
                        frame_number=thread_id,
                        timestamp=thread_id * 0.1,
                        class_label="pedestrian",
                        x=100.0,
                        y=200.0,
                        width=80.0,
                        height=160.0,
                        confidence=0.8,
                        validated=True,
                        difficult=False
                    )
                    db.add(gt_object)
                    
                    # Sleep to allow other transactions to interfere
                    time.sleep(0.1)
                    
                    # Check count again (should be isolated)
                    mid_count = db.query(GroundTruthObject).filter(
                        GroundTruthObject.video_id == video.id
                    ).count()
                    
                    # Commit
                    db.commit()
                    
                    # Final count
                    final_count = db.query(GroundTruthObject).filter(
                        GroundTruthObject.video_id == video.id
                    ).count()
                    
                    return {
                        "thread_id": thread_id,
                        "initial_count": initial_count,
                        "mid_count": mid_count,
                        "final_count": final_count,
                        "status": "success"
                    }
                    
                except Exception as e:
                    db.rollback()
                    raise e
                finally:
                    db.close()
                    
            except Exception as e:
                return {
                    "thread_id": thread_id,
                    "status": "error",
                    "error": str(e)
                }
        
        # Act - Run concurrent transactions
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(transaction_test, i) for i in range(3)]
            isolation_test_results = [future.result() for future in as_completed(futures)]
        
        # Assert - Transactions should be isolated
        success_results = [r for r in isolation_test_results if r.get("status") == "success"]
        assert len(success_results) == 3, "Not all transactions completed successfully"
        
        # Verify final state
        db = SessionLocal()
        try:
            final_total = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).count()
            assert final_total == 3, f"Expected 3 objects, found {final_total}"
        finally:
            db.close()

class TestRaceConditionPrevention:
    """Test prevention of race conditions"""
    
    def test_duplicate_processing_prevention(self, concurrency_helper):
        """Test prevention of duplicate video processing"""
        # Arrange
        project = concurrency_helper.create_test_project()
        video = concurrency_helper.create_test_video(project.id)
        
        processing_attempts = []
        
        def attempt_processing(attempt_id):
            """Attempt to process the same video"""
            try:
                service = GroundTruthService()
                
                # Mock the processing to make it deterministic
                with patch.object(service, '_extract_detections') as mock_extract:
                    mock_extract.return_value = [
                        {
                            "frame_number": 20,
                            "timestamp": 0.67,
                            "class_label": "pedestrian",
                            "x": 120.0,
                            "y": 210.0,
                            "width": 85.0,
                            "height": 165.0,
                            "confidence": 0.88,
                            "validated": True,
                            "difficult": False
                        }
                    ]
                    
                    # Add small delay to increase chance of race condition
                    time.sleep(0.05)
                    
                    service._process_video(video.id, video.file_path)
                    return {"attempt_id": attempt_id, "status": "success"}
                    
            except Exception as e:
                return {"attempt_id": attempt_id, "status": "error", "error": str(e)}
        
        # Act - Attempt concurrent processing of same video
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(attempt_processing, i) for i in range(3)]
            processing_attempts = [future.result() for future in as_completed(futures)]
        
        # Assert - Only one should succeed or all should succeed gracefully
        success_count = sum(1 for r in processing_attempts if r.get("status") == "success")
        
        # Either all succeed (if processing is idempotent) or only one succeeds
        assert success_count >= 1, "At least one processing attempt should succeed"
        
        # Verify video state is consistent
        db = SessionLocal()
        try:
            video_state = db.query(Video).filter(Video.id == video.id).first()
            assert video_state.ground_truth_generated is True
            assert video_state.status in ["validated", "completed"]
        finally:
            db.close()
    
    def test_concurrent_status_updates(self, concurrency_helper):
        """Test concurrent status updates on the same video"""
        # Arrange
        project = concurrency_helper.create_test_project()
        video = concurrency_helper.create_test_video(project.id)
        
        status_updates = []
        
        def update_video_status(thread_id, new_status):
            """Update video status"""
            try:
                db = SessionLocal()
                try:
                    video_record = db.query(Video).filter(Video.id == video.id).first()
                    if video_record:
                        video_record.status = new_status
                        video_record.processing_status = "completed" if new_status == "validated" else "processing"
                        db.commit()
                        return {"thread_id": thread_id, "status": "success", "new_status": new_status}
                    else:
                        return {"thread_id": thread_id, "status": "error", "error": "Video not found"}
                finally:
                    db.close()
            except Exception as e:
                return {"thread_id": thread_id, "status": "error", "error": str(e)}
        
        # Act - Concurrent status updates
        statuses = ["processing", "validated", "completed"]
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(update_video_status, i, statuses[i]) 
                for i in range(3)
            ]
            status_updates = [future.result() for future in as_completed(futures)]
        
        # Assert - All updates should succeed
        success_count = sum(1 for r in status_updates if r.get("status") == "success")
        assert success_count == 3, f"Expected 3 successful updates, got {success_count}"
        
        # Verify final state is consistent (last update wins)
        db = SessionLocal()
        try:
            final_video = db.query(Video).filter(Video.id == video.id).first()
            assert final_video.status in statuses, f"Final status {final_video.status} not in expected statuses"
        finally:
            db.close()

class TestDeadlockPrevention:
    """Test deadlock prevention in concurrent operations"""
    
    def test_ordered_resource_access(self, concurrency_helper):
        """Test that resources are accessed in consistent order to prevent deadlocks"""
        # Arrange
        project = concurrency_helper.create_test_project()
        video1 = concurrency_helper.create_test_video(project.id)
        video2 = concurrency_helper.create_test_video(project.id)
        
        def cross_video_operation(thread_id):
            """Perform operations across multiple videos"""
            try:
                db = SessionLocal()
                try:
                    # Access videos in consistent order (by ID) to prevent deadlocks
                    video_ids = sorted([video1.id, video2.id])
                    
                    for video_id in video_ids:
                        # Lock video for update
                        video = db.query(Video).filter(Video.id == video_id).with_for_update().first()
                        
                        if video:
                            # Create ground truth object
                            gt_object = GroundTruthObject(
                                id=str(uuid.uuid4()),
                                video_id=video_id,
                                frame_number=thread_id * 10,
                                timestamp=thread_id * 0.1,
                                class_label="pedestrian",
                                x=100.0,
                                y=200.0,
                                width=80.0,
                                height=160.0,
                                confidence=0.8,
                                validated=True,
                                difficult=False
                            )
                            db.add(gt_object)
                    
                    db.commit()
                    return {"thread_id": thread_id, "status": "success"}
                    
                except Exception as e:
                    db.rollback()
                    raise e
                finally:
                    db.close()
                    
            except Exception as e:
                return {"thread_id": thread_id, "status": "error", "error": str(e)}
        
        # Act - Run potentially deadlocking operations
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(cross_video_operation, i) for i in range(4)]
            results = [future.result() for future in as_completed(futures)]
        
        # Assert - All operations should complete without deadlock
        success_count = sum(1 for r in results if r.get("status") == "success")
        error_count = sum(1 for r in results if r.get("status") == "error")
        
        # All should succeed if deadlock prevention works
        assert success_count == 4, f"Expected 4 successes, got {success_count}. Errors: {error_count}"

class TestResourceContention:
    """Test handling of resource contention"""
    
    def test_file_access_contention(self, concurrency_helper):
        """Test handling of file access contention"""
        # Arrange
        project = concurrency_helper.create_test_project()
        
        # Create a shared temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_file.write(b"fake video data")
        temp_file.close()
        
        # Create multiple videos pointing to same file
        videos = []
        for i in range(3):
            video = Video(
                id=str(uuid.uuid4()),
                filename=f"shared_video_{i}.mp4",
                file_path=temp_file.name,
                file_size=len(b"fake video data"),
                duration=5.0,
                fps=30.0,
                resolution="640x480",
                status="uploaded",
                processing_status="pending",
                ground_truth_generated=False,
                project_id=project.id
            )
            videos.append(video)
            concurrency_helper.test_videos.append(video.id)
        
        db = SessionLocal()
        try:
            for video in videos:
                db.add(video)
            db.commit()
        finally:
            db.close()
        
        def process_shared_file(video):
            """Process video with shared file"""
            try:
                # Simulate file processing with contention
                time.sleep(0.1)  # Simulate processing time
                
                # Check if file exists and is accessible
                if os.path.exists(video.file_path):
                    with open(video.file_path, 'rb') as f:
                        data = f.read()
                        assert len(data) > 0, "File should not be empty"
                
                return {"video_id": video.id, "status": "success"}
                
            except Exception as e:
                return {"video_id": video.id, "status": "error", "error": str(e)}
        
        try:
            # Act - Process shared file concurrently
            results = []
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(process_shared_file, video) for video in videos]
                results = [future.result() for future in as_completed(futures)]
            
            # Assert - All should handle file access gracefully
            success_count = sum(1 for r in results if r.get("status") == "success")
            assert success_count == 3, f"Expected 3 successes, got {success_count}"
            
        finally:
            # Cleanup
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])