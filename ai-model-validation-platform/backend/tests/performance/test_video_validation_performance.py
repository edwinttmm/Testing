"""
Performance Tests for Video Validation Batch Operations
=======================================================

Tests performance of video validation operations under load and with large datasets.
"""

import pytest
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import tempfile
import os
from typing import List, Dict, Any

from database import Base
from models import Project, Video, GroundTruthObject, TestSession, DetectionEvent
from crud import (
    create_video, update_video_status, get_videos, 
    bulk_assign_videos_to_project, bulk_remove_videos_from_project
)


# Performance test database
PERF_DB_URL = "sqlite:///./test_performance_video_validation.db"
perf_engine = create_engine(PERF_DB_URL, connect_args={"check_same_thread": False})
PerfSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=perf_engine)


@pytest.fixture(scope="module")
def perf_db():
    """Performance test database fixture"""
    Base.metadata.create_all(bind=perf_engine)
    yield PerfSessionLocal()
    Base.metadata.drop_all(bind=perf_engine)
    try:
        os.unlink(PERF_DB_URL.replace("sqlite:///./", ""))
    except FileNotFoundError:
        pass


@pytest.fixture
def large_dataset(perf_db):
    """Create large dataset for performance testing"""
    # Create test project
    project = Project(
        id="perf-test-project",
        name="Performance Test Project", 
        description="Project for performance testing",
        camera_model="Perf Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        owner_id="perf-user"
    )
    perf_db.add(project)
    
    # Create 1000 videos with various statuses
    videos = []
    status_distribution = [
        ("uploaded", 300),
        ("processing", 250),
        ("pending_validation", 200),
        ("validated", 200), 
        ("error", 50)
    ]
    
    video_id = 1
    for status, count in status_distribution:
        for i in range(count):
            video = Video(
                id=f"perf-video-{video_id}",
                filename=f"perf_video_{video_id}.mp4",
                file_path=f"/uploads/perf_video_{video_id}.mp4", 
                status=status,
                processing_status="completed" if status == "validated" else "pending",
                ground_truth_generated=(status in ["validated", "pending_validation"]),
                project_id=project.id,
                file_size=1024 * 1024 * 10,  # 10MB
                duration=30.0,
                fps=30.0
            )
            perf_db.add(video)
            videos.append(video)
            video_id += 1
    
    perf_db.commit()
    return {"project": project, "videos": videos}


class TestVideoQueryPerformance:
    """Test performance of video query operations"""
    
    def test_large_video_listing_performance(self, perf_db, large_dataset):
        """Test performance of listing large numbers of videos"""
        project_id = large_dataset["project"].id
        
        # Test query performance
        start_time = time.time()
        videos = perf_db.query(Video).filter(Video.project_id == project_id).all()
        query_time = time.time() - start_time
        
        assert len(videos) == 1000
        assert query_time < 1.0  # Should complete in under 1 second
    
    def test_video_status_filtering_performance(self, perf_db, large_dataset):
        """Test performance of filtering videos by status"""
        project_id = large_dataset["project"].id
        
        # Test filtering by single status
        start_time = time.time()
        validated_videos = perf_db.query(Video).filter(
            Video.project_id == project_id,
            Video.status == "validated"
        ).all()
        single_filter_time = time.time() - start_time
        
        assert len(validated_videos) == 200
        assert single_filter_time < 0.5
        
        # Test filtering by multiple statuses 
        start_time = time.time()
        multiple_status_videos = perf_db.query(Video).filter(
            Video.project_id == project_id,
            Video.status.in_(["validated", "pending_validation"])
        ).all()
        multiple_filter_time = time.time() - start_time
        
        assert len(multiple_status_videos) == 400
        assert multiple_filter_time < 0.5
    
    def test_paginated_video_queries_performance(self, perf_db, large_dataset):
        """Test performance of paginated video queries"""
        project_id = large_dataset["project"].id
        page_size = 50
        
        # Test multiple pages
        page_times = []
        for page in range(5):  # Test first 5 pages
            start_time = time.time()
            videos = perf_db.query(Video).filter(
                Video.project_id == project_id
            ).offset(page * page_size).limit(page_size).all()
            page_time = time.time() - start_time
            page_times.append(page_time)
            
            assert len(videos) == page_size
        
        # All pages should load quickly
        max_page_time = max(page_times)
        avg_page_time = statistics.mean(page_times)
        
        assert max_page_time < 0.2
        assert avg_page_time < 0.1
    
    def test_video_aggregation_queries_performance(self, perf_db, large_dataset):
        """Test performance of video aggregation queries"""
        project_id = large_dataset["project"].id
        
        # Test status count aggregation
        start_time = time.time()
        status_counts = perf_db.query(
            Video.status,
            func.count(Video.id).label('count')
        ).filter(
            Video.project_id == project_id
        ).group_by(Video.status).all()
        aggregation_time = time.time() - start_time
        
        assert len(status_counts) == 5  # 5 different statuses
        assert aggregation_time < 0.5
        
        # Verify counts
        status_dict = {status: count for status, count in status_counts}
        assert status_dict["uploaded"] == 300
        assert status_dict["validated"] == 200


class TestBatchVideoOperationsPerformance:
    """Test performance of batch video operations"""
    
    def test_batch_status_update_performance(self, perf_db, large_dataset):
        """Test performance of batch video status updates"""
        # Get videos to update (all processing videos)
        processing_videos = perf_db.query(Video).filter(
            Video.status == "processing"
        ).all()
        
        assert len(processing_videos) == 250
        
        # Test batch update performance
        start_time = time.time()
        
        for video in processing_videos:
            video.status = "validated"
            video.ground_truth_generated = True
        
        perf_db.commit()
        batch_update_time = time.time() - start_time
        
        # Batch update should complete in reasonable time
        assert batch_update_time < 5.0  # Under 5 seconds for 250 updates
        
        # Verify updates
        validated_count = perf_db.query(Video).filter(Video.status == "validated").count()
        assert validated_count == 450  # 200 original + 250 updated
    
    def test_bulk_ground_truth_assignment_performance(self, perf_db, large_dataset):
        """Test performance of bulk ground truth assignment"""
        # Get videos that need ground truth
        videos_needing_gt = perf_db.query(Video).filter(
            Video.ground_truth_generated == False
        ).limit(100).all()  # Test with 100 videos
        
        # Create ground truth objects in bulk
        start_time = time.time()
        
        ground_truth_objects = []
        for video in videos_needing_gt:
            # Create 3 ground truth objects per video
            for i in range(3):
                gt = GroundTruthObject(
                    id=f"bulk-gt-{video.id}-{i}",
                    video_id=video.id,
                    timestamp=i * 2.0,
                    class_label="pedestrian",
                    x=100 + i * 50,
                    y=100 + i * 30,
                    width=50,
                    height=100,
                    confidence=0.9,
                    validated=True
                )
                ground_truth_objects.append(gt)
        
        # Bulk insert
        perf_db.bulk_save_objects(ground_truth_objects)
        
        # Update video statuses
        for video in videos_needing_gt:
            video.ground_truth_generated = True
            video.processing_status = "completed"
        
        perf_db.commit()
        bulk_gt_time = time.time() - start_time
        
        assert bulk_gt_time < 3.0  # Under 3 seconds for 100 videos * 3 GT objects
        assert len(ground_truth_objects) == 300  # 100 videos * 3 GT objects each
    
    def test_concurrent_video_status_updates(self, perf_db, large_dataset):
        """Test performance under concurrent video status updates"""
        # Get videos for concurrent updates
        videos_to_update = perf_db.query(Video).filter(
            Video.status == "uploaded"
        ).limit(50).all()
        
        def update_video_status_worker(video_ids: List[str]):
            """Worker function for concurrent updates"""
            worker_db = PerfSessionLocal()
            try:
                for video_id in video_ids:
                    video = worker_db.query(Video).filter(Video.id == video_id).first()
                    if video:
                        video.status = "processing"
                        worker_db.commit()
            finally:
                worker_db.close()
        
        # Split videos into batches for concurrent processing
        batch_size = 10
        video_batches = [
            [v.id for v in videos_to_update[i:i + batch_size]]
            for i in range(0, len(videos_to_update), batch_size)
        ]
        
        # Test concurrent updates
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(update_video_status_worker, batch)
                for batch in video_batches
            ]
            
            for future in as_completed(futures):
                future.result()  # Wait for completion
        
        concurrent_update_time = time.time() - start_time
        
        # Concurrent updates should be faster than sequential
        assert concurrent_update_time < 10.0
        
        # Verify all videos were updated
        updated_videos = perf_db.query(Video).filter(
            Video.id.in_([v.id for v in videos_to_update]),
            Video.status == "processing"
        ).count()
        assert updated_videos == 50


class TestVideoValidationWorkflowPerformance:
    """Test performance of complete video validation workflows"""
    
    def test_full_validation_workflow_performance(self, perf_db, large_dataset):
        """Test performance of complete validation workflow"""
        # Select videos for full workflow testing
        uploaded_videos = perf_db.query(Video).filter(
            Video.status == "uploaded"
        ).limit(50).all()
        
        workflow_times = {
            "status_updates": [],
            "ground_truth_generation": [],
            "validation_checks": []
        }
        
        for video in uploaded_videos:
            # Step 1: Update to processing
            start_time = time.time()
            video.status = "processing"
            perf_db.commit()
            workflow_times["status_updates"].append(time.time() - start_time)
            
            # Step 2: Generate ground truth
            start_time = time.time()
            gt_objects = []
            for i in range(5):  # 5 ground truth objects per video
                gt = GroundTruthObject(
                    id=f"workflow-gt-{video.id}-{i}",
                    video_id=video.id,
                    timestamp=i * 1.5,
                    class_label="pedestrian",
                    x=100 + i * 40,
                    y=100 + i * 20,
                    width=50,
                    height=100,
                    confidence=0.9,
                    validated=True
                )
                gt_objects.append(gt)
            
            perf_db.bulk_save_objects(gt_objects)
            video.ground_truth_generated = True
            video.processing_status = "completed"
            perf_db.commit()
            workflow_times["ground_truth_generation"].append(time.time() - start_time)
            
            # Step 3: Validation checks
            start_time = time.time()
            # Check if video meets validation criteria
            gt_count = perf_db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).count()
            
            validated_gt_count = perf_db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id,
                GroundTruthObject.validated == True
            ).count()
            
            if gt_count > 0 and validated_gt_count == gt_count:
                video.status = "validated"
            else:
                video.status = "pending_validation"
            
            perf_db.commit()
            workflow_times["validation_checks"].append(time.time() - start_time)
        
        # Analyze workflow performance
        avg_status_update_time = statistics.mean(workflow_times["status_updates"])
        avg_gt_generation_time = statistics.mean(workflow_times["ground_truth_generation"])
        avg_validation_check_time = statistics.mean(workflow_times["validation_checks"])
        
        # Performance assertions
        assert avg_status_update_time < 0.1  # Status updates should be very fast
        assert avg_gt_generation_time < 0.5  # GT generation should be reasonable
        assert avg_validation_check_time < 0.2  # Validation checks should be fast
        
        print(f"Average workflow times:")
        print(f"  Status updates: {avg_status_update_time:.3f}s")
        print(f"  Ground truth generation: {avg_gt_generation_time:.3f}s")
        print(f"  Validation checks: {avg_validation_check_time:.3f}s")
    
    def test_hil_test_eligibility_check_performance(self, perf_db, large_dataset):
        """Test performance of HIL test eligibility checking"""
        # Test performance of finding HIL-eligible videos
        start_time = time.time()
        
        hil_eligible_videos = perf_db.query(Video).filter(
            Video.status == "validated",
            Video.ground_truth_generated == True,
            Video.processing_status == "completed"
        ).all()
        
        eligibility_check_time = time.time() - start_time
        
        assert eligibility_check_time < 0.5
        assert len(hil_eligible_videos) > 0
        
        # Test performance of eligibility check with additional criteria
        start_time = time.time()
        
        # More complex eligibility check including ground truth validation
        eligible_with_gt_check = []
        for video in hil_eligible_videos[:50]:  # Test first 50 to avoid timeout
            gt_count = perf_db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id,
                GroundTruthObject.validated == True
            ).count()
            
            if gt_count >= 3:  # Minimum 3 validated ground truth objects
                eligible_with_gt_check.append(video)
        
        complex_eligibility_time = time.time() - start_time
        
        assert complex_eligibility_time < 2.0  # Should complete in under 2 seconds
        print(f"HIL eligibility check times:")
        print(f"  Basic check: {eligibility_check_time:.3f}s")
        print(f"  Complex check: {complex_eligibility_time:.3f}s")


class TestVideoValidationMemoryUsage:
    """Test memory usage during video validation operations"""
    
    def test_memory_efficient_batch_processing(self, perf_db, large_dataset):
        """Test memory usage during batch video processing"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Measure memory before batch processing
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process videos in batches to control memory usage
        batch_size = 100
        total_processed = 0
        
        video_query = perf_db.query(Video).filter(Video.status == "uploaded")
        total_videos = video_query.count()
        
        for offset in range(0, total_videos, batch_size):
            batch_videos = video_query.offset(offset).limit(batch_size).all()
            
            # Process batch
            for video in batch_videos:
                video.status = "processing"
            
            perf_db.commit()
            total_processed += len(batch_videos)
            
            # Clear SQLAlchemy session to free memory
            perf_db.expunge_all()
        
        # Measure memory after batch processing
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        # Memory increase should be reasonable (less than 50MB for batch processing)
        assert memory_increase < 50.0
        assert total_processed > 0
        
        print(f"Memory usage for batch processing:")
        print(f"  Before: {memory_before:.2f} MB")
        print(f"  After: {memory_after:.2f} MB")
        print(f"  Increase: {memory_increase:.2f} MB")
        print(f"  Videos processed: {total_processed}")
    
    def test_large_result_set_memory_usage(self, perf_db, large_dataset):
        """Test memory usage when handling large result sets"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Query large result set using iterator to control memory
        video_count = 0
        for video in perf_db.query(Video).yield_per(50):  # Process 50 at a time
            video_count += 1
            # Simulate some processing
            _ = video.filename
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        # Using yield_per should keep memory usage low
        assert memory_increase < 30.0  # Should not increase by more than 30MB
        assert video_count == 1000
        
        print(f"Large result set memory usage:")
        print(f"  Memory increase: {memory_increase:.2f} MB")
        print(f"  Videos processed: {video_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to show print outputs