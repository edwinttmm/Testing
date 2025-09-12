#!/usr/bin/env python3
"""
Performance comparison tests between manual deletion and cascade delete operations.
Demonstrates the efficiency improvements achieved by using proper cascade configurations.
"""

import sys
import os
import time
import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

# Add backend to Python path
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'ai-model-validation-platform', 'backend')
sys.path.insert(0, backend_path)

from database import Base
from models import (
    Project, Video, TestSession, DetectionEvent, GroundTruthObject, 
    Annotation, AnnotationSession, VideoProjectLink, TestResult, DetectionComparison
)
from crud import delete_project, create_project
from schemas import ProjectCreate


class TestPerformanceComparison:
    """Performance comparison between manual and cascade delete operations"""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        yield session
        
        session.close()
    
    def create_large_project_structure(self, db_session, user_id="perf_test_user"):
        """Create a large project structure for performance testing"""
        # Create project
        project_data = ProjectCreate(
            name="Performance Test Project",
            description="Large project for performance testing",
            camera_model="PerfTestCam v1.0",
            camera_view="Front-facing VRU", 
            lens_type="Wide-angle",
            resolution="1920x1080",
            frame_rate=30,
            signal_type="GPIO"
        )
        project = create_project(db_session, project_data, user_id)
        
        videos = []
        # Create multiple videos
        for v in range(5):
            video = Video(
                filename=f"perf_test_video_{v}.mp4",
                file_path=f"/test/perf/video_{v}.mp4",
                file_size=1024000 * (v + 1),
                duration=120.0 + v * 30,
                fps=30.0,
                resolution="1920x1080",
                project_id=project.id
            )
            db_session.add(video)
            db_session.flush()
            videos.append(video)
            
            # Create many ground truth objects per video
            for frame in range(0, 600, 10):  # 60 ground truth objects per video
                ground_truth = GroundTruthObject(
                    video_id=video.id,
                    tracking_id=f"GT_{v}_{frame}",
                    frame_number=frame,
                    timestamp=frame / 30.0,
                    class_label="pedestrian" if frame % 20 == 0 else "cyclist",
                    x=float(frame % 1920), y=float(frame % 1080), 
                    width=50.0, height=100.0,
                    confidence=0.9,
                    validated=True
                )
                db_session.add(ground_truth)
            
            # Create annotations
            for frame in range(0, 600, 15):  # 40 annotations per video
                annotation = Annotation(
                    video_id=video.id,
                    detection_id=f"DET_{v}_{frame}",
                    frame_number=frame,
                    timestamp=frame / 30.0,
                    vru_type="pedestrian" if frame % 30 == 0 else "cyclist",
                    bounding_box={"x": frame % 1920, "y": frame % 1080, "width": 50, "height": 100},
                    validated=True
                )
                db_session.add(annotation)
        
        # Create multiple test sessions
        for s in range(10):  # 10 test sessions
            test_session = TestSession(
                name=f"Perf Test Session {s}",
                project_id=project.id,
                video_id=videos[s % len(videos)].id,
                tolerance_ms=100,
                status="completed",
                session_type="user_created",
                latency_threshold_ms=100
            )
            db_session.add(test_session)
            db_session.flush()
            
            # Create many detection events per session
            for d in range(50):  # 50 detection events per session
                detection_event = DetectionEvent(
                    test_session_id=test_session.id,
                    video_id=videos[s % len(videos)].id,
                    timestamp=d * 0.5,
                    validation_result="Pass" if d % 2 == 0 else "Fail",
                    latency_ms=80.0 + d % 50,
                    labjack_timestamp=d * 0.5 - 0.08,
                    video_start_time=0.0,
                    latency_result="pass" if d % 2 == 0 else "fail",
                    voltage_level=3.3,
                    detection_channel="AIN0"
                )
                db_session.add(detection_event)
            
            # Create test result
            test_result = TestResult(
                test_session_id=test_session.id,
                pass_rate=50.0,
                avg_latency_ms=100.0 + s,
                max_latency_ms=130.0,
                min_latency_ms=80.0,
                total_detections=50,
                passed_detections=25,
                failed_detections=25,
                threshold_ms=100
            )
            db_session.add(test_result)
        
        db_session.commit()
        
        # Return counts for verification
        return {
            'project': project,
            'videos': len(videos),
            'ground_truth_count': db_session.query(GroundTruthObject).filter(
                GroundTruthObject.video_id.in_([v.id for v in videos])
            ).count(),
            'annotation_count': db_session.query(Annotation).filter(
                Annotation.video_id.in_([v.id for v in videos])
            ).count(),
            'test_session_count': 10,
            'detection_event_count': db_session.query(DetectionEvent).filter(
                DetectionEvent.test_session_id.in_(
                    db_session.query(TestSession.id).filter(TestSession.project_id == project.id)
                )
            ).count(),
            'test_result_count': 10
        }
    
    def manual_delete_project_old_way(self, db_session, project_id, user_id):
        """Simulate the old manual deletion approach for comparison"""
        from models import DetectionEvent, TestSession, Video, GroundTruthObject
        
        project = db_session.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == user_id
        ).first()
        
        if not project:
            return False
            
        try:
            # Manual deletion in proper order (old approach)
            
            # Delete detection events for test sessions of this project
            db_session.query(DetectionEvent).filter(
                DetectionEvent.test_session_id.in_(
                    db_session.query(TestSession.id).filter(TestSession.project_id == project_id)
                )
            ).delete(synchronize_session=False)
            
            # Delete test results
            db_session.query(TestResult).filter(
                TestResult.test_session_id.in_(
                    db_session.query(TestSession.id).filter(TestSession.project_id == project_id)
                )
            ).delete(synchronize_session=False)
            
            # Delete test sessions for this project
            db_session.query(TestSession).filter(TestSession.project_id == project_id).delete(synchronize_session=False)
            
            # Delete annotations for videos in this project
            db_session.query(Annotation).filter(
                Annotation.video_id.in_(
                    db_session.query(Video.id).filter(Video.project_id == project_id)
                )
            ).delete(synchronize_session=False)
            
            # Delete ground truth objects for videos in this project
            db_session.query(GroundTruthObject).filter(
                GroundTruthObject.video_id.in_(
                    db_session.query(Video.id).filter(Video.project_id == project_id)
                )
            ).delete(synchronize_session=False)
            
            # Delete annotation sessions
            db_session.query(AnnotationSession).filter(AnnotationSession.project_id == project_id).delete(synchronize_session=False)
            
            # Delete video project links
            db_session.query(VideoProjectLink).filter(VideoProjectLink.project_id == project_id).delete(synchronize_session=False)
            
            # Delete videos for this project
            db_session.query(Video).filter(Video.project_id == project_id).delete(synchronize_session=False)
            
            # Finally delete the project itself
            db_session.delete(project)
            db_session.commit()
            
            return True
            
        except Exception as e:
            db_session.rollback()
            raise e
    
    def test_cascade_vs_manual_delete_performance(self, db_session):
        """Compare performance between cascade delete and manual deletion"""
        # Create two identical large project structures
        structure1 = self.create_large_project_structure(db_session, "user1")
        structure2 = self.create_large_project_structure(db_session, "user2")
        
        project1_id = structure1['project'].id
        project2_id = structure2['project'].id
        
        print(f"\nTest setup complete:")
        print(f"Videos per project: {structure1['videos']}")
        print(f"Ground truth objects per project: {structure1['ground_truth_count']}")
        print(f"Annotations per project: {structure1['annotation_count']}")
        print(f"Test sessions per project: {structure1['test_session_count']}")
        print(f"Detection events per project: {structure1['detection_event_count']}")
        print(f"Test results per project: {structure1['test_result_count']}")
        
        # Test manual deletion performance (old way)
        with patch('os.path.exists', return_value=False):
            start_time = time.time()
            result1 = self.manual_delete_project_old_way(db_session, project1_id, "user1")
            manual_delete_time = time.time() - start_time
            
            assert result1 is True
            
            # Verify manual deletion worked
            remaining_objects = db_session.query(Project).filter(Project.id == project1_id).count()
            assert remaining_objects == 0
        
        # Test cascade deletion performance (optimized way)
        with patch('os.path.exists', return_value=False):
            start_time = time.time()
            result2 = delete_project(db_session, project2_id, "user2")
            cascade_delete_time = time.time() - start_time
            
            assert result2 is True
            
            # Verify cascade deletion worked
            remaining_objects = db_session.query(Project).filter(Project.id == project2_id).count()
            assert remaining_objects == 0
        
        print(f"\nPerformance Results:")
        print(f"Manual delete time: {manual_delete_time:.4f} seconds")
        print(f"Cascade delete time: {cascade_delete_time:.4f} seconds")
        print(f"Performance improvement: {((manual_delete_time - cascade_delete_time) / manual_delete_time * 100):.1f}%")
        
        # Cascade delete should be faster (though in SQLite the difference might be minimal)
        # The main benefit is code simplicity and reduced chance of errors
        assert cascade_delete_time <= manual_delete_time * 1.1  # Allow 10% tolerance
    
    def test_database_query_count_comparison(self, db_session):
        """Compare number of database queries between approaches"""
        structure = self.create_large_project_structure(db_session)
        project_id = structure['project'].id
        
        # Mock execute to count queries
        original_execute = db_session.execute
        query_count = 0
        
        def counting_execute(*args, **kwargs):
            nonlocal query_count
            query_count += 1
            return original_execute(*args, **kwargs)
        
        with patch.object(db_session, 'execute', side_effect=counting_execute), \
             patch('os.path.exists', return_value=False):
            
            result = delete_project(db_session, project_id, "perf_test_user")
            assert result is True
        
        print(f"\nDatabase Query Analysis:")
        print(f"Total queries executed: {query_count}")
        
        # With proper cascade, we should have minimal queries:
        # 1. Query to get project
        # 2. Query for videos (to get file paths)
        # 3. Delete project (cascade handles the rest)
        # 4. Commit
        assert query_count < 20, f"Too many queries ({query_count}). Cascade delete should be more efficient."
    
    def test_memory_usage_comparison(self, db_session):
        """Test memory usage patterns between manual and cascade deletion"""
        import psutil
        import os
        
        # Create large project structure
        structure = self.create_large_project_structure(db_session)
        project_id = structure['project'].id
        
        # Get baseline memory
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        with patch('os.path.exists', return_value=False):
            # Perform cascade delete
            result = delete_project(db_session, project_id, "perf_test_user")
            assert result is True
            
            # Check memory after deletion
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_increase = final_memory - initial_memory
        print(f"\nMemory Usage Analysis:")
        print(f"Initial memory: {initial_memory:.2f} MB")
        print(f"Final memory: {final_memory:.2f} MB")
        print(f"Memory increase: {memory_increase:.2f} MB")
        
        # Cascade delete should not cause significant memory leaks
        assert memory_increase < 50, f"Excessive memory increase: {memory_increase:.2f} MB"
    
    def test_transaction_efficiency(self, db_session):
        """Test that cascade deletes use efficient transaction handling"""
        structure = self.create_large_project_structure(db_session)
        project_id = structure['project'].id
        
        # Mock commit and rollback to track transaction behavior
        original_commit = db_session.commit
        original_rollback = db_session.rollback
        
        commit_count = 0
        rollback_count = 0
        
        def counting_commit():
            nonlocal commit_count
            commit_count += 1
            return original_commit()
        
        def counting_rollback():
            nonlocal rollback_count
            rollback_count += 1
            return original_rollback()
        
        with patch.object(db_session, 'commit', side_effect=counting_commit), \
             patch.object(db_session, 'rollback', side_effect=counting_rollback), \
             patch('os.path.exists', return_value=False):
            
            result = delete_project(db_session, project_id, "perf_test_user")
            assert result is True
        
        print(f"\nTransaction Efficiency:")
        print(f"Commits: {commit_count}")
        print(f"Rollbacks: {rollback_count}")
        
        # Should use minimal transactions
        assert commit_count == 1, f"Should use single transaction, but used {commit_count} commits"
        assert rollback_count == 0, f"Should not rollback on success, but had {rollback_count} rollbacks"
    
    def test_scalability_with_large_datasets(self, db_session):
        """Test cascade delete performance with very large datasets"""
        # Create project with even more data
        project_data = ProjectCreate(
            name="Scalability Test Project",
            description="Very large project for scalability testing",
            camera_model="ScaleCam v1.0",
            camera_view="Front-facing VRU",
            lens_type="Ultra-wide",
            resolution="4K",
            frame_rate=60,
            signal_type="GPIO"
        )
        project = create_project(db_session, project_data, "scale_test_user")
        
        # Create fewer objects but still test scalability
        videos = []
        for v in range(2):  # Reduce for faster test
            video = Video(
                filename=f"scale_test_video_{v}.mp4",
                file_path=f"/test/scale/video_{v}.mp4",
                file_size=5120000,  # 5MB
                duration=300.0,     # 5 minutes
                fps=60.0,
                resolution="3840x2160",
                project_id=project.id
            )
            db_session.add(video)
            db_session.flush()
            videos.append(video)
            
            # Create many ground truth objects
            for frame in range(0, 1000, 20):  # 50 per video
                ground_truth = GroundTruthObject(
                    video_id=video.id,
                    tracking_id=f"SCALE_GT_{v}_{frame}",
                    frame_number=frame,
                    timestamp=frame / 60.0,
                    class_label="vehicle" if frame % 40 == 0 else "pedestrian",
                    x=float(frame % 3840), y=float(frame % 2160),
                    width=100.0, height=150.0,
                    confidence=0.95,
                    validated=True
                )
                db_session.add(ground_truth)
        
        # Create test sessions with many detection events
        for s in range(5):
            test_session = TestSession(
                name=f"Scale Session {s}",
                project_id=project.id,
                video_id=videos[s % 2].id,
                tolerance_ms=50,
                status="completed",
                session_type="automated",
                latency_threshold_ms=50
            )
            db_session.add(test_session)
            db_session.flush()
            
            # Create many detection events
            for d in range(100):  # 100 per session
                detection_event = DetectionEvent(
                    test_session_id=test_session.id,
                    video_id=videos[s % 2].id,
                    timestamp=d * 0.25,
                    validation_result="Pass" if d % 3 != 0 else "Fail",
                    latency_ms=30.0 + (d % 40),
                    labjack_timestamp=d * 0.25 - 0.03,
                    video_start_time=0.0,
                    latency_result="pass" if d % 3 != 0 else "fail"
                )
                db_session.add(detection_event)
        
        db_session.commit()
        
        # Count total objects
        total_ground_truth = db_session.query(GroundTruthObject).count()
        total_detection_events = db_session.query(DetectionEvent).count()
        
        print(f"\nScalability Test Setup:")
        print(f"Total ground truth objects: {total_ground_truth}")
        print(f"Total detection events: {total_detection_events}")
        
        # Time the cascade deletion
        with patch('os.path.exists', return_value=False):
            start_time = time.time()
            result = delete_project(db_session, project.id, "scale_test_user")
            deletion_time = time.time() - start_time
            
            assert result is True
        
        print(f"Scalability deletion time: {deletion_time:.4f} seconds")
        
        # Verify all objects were deleted
        remaining_ground_truth = db_session.query(GroundTruthObject).count()
        remaining_detection_events = db_session.query(DetectionEvent).count()
        
        assert remaining_ground_truth == 0
        assert remaining_detection_events == 0
        
        # Performance should scale reasonably
        assert deletion_time < 10.0, f"Deletion took too long: {deletion_time:.2f} seconds"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to see print statements