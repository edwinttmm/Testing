"""
Database Integration Tests for HIL System

Tests database operations, model relationships, and data integrity
for the HIL ground truth matching system.

Test Coverage:
- Model relationships and foreign keys
- Database schema validation
- Transaction handling and rollback scenarios
- Data integrity constraints
- Index performance validation
- Concurrent database operations
"""

import pytest
import sys
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, select, delete, update, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Import the models and services
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')
from models import (
    TestSession, DetectionEvent, TestResult, Video, Project,
    DetectionComparison, GroundTruthObject, Base
)
from database import SessionLocal


class TestDatabaseIntegration:
    """Test suite for database integration and data integrity"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def test_project(self, db_session: Session):
        """Create a test project"""
        project = Project(
            name="Database Integration Test Project",
            description="Testing database operations",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active"
        )
        db_session.add(project)
        db_session.commit()
        return project
    
    @pytest.fixture
    def test_video(self, db_session: Session, test_project):
        """Create a test video"""
        video = Video(
            filename="db_test_video.mp4",
            file_path="/test/db_test_video.mp4",
            file_size=1000000,
            duration=10.0,
            fps=30.0,
            resolution="1920x1080",
            status="validated",
            project_id=test_project.id,
            ground_truth_count=10
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    def test_model_relationships_integrity(self, db_session: Session, test_project, test_video):
        """Test that model relationships work correctly"""
        # Create test session
        test_session = TestSession(
            name="Relationship Test Session",
            project_id=test_project.id,
            status="running",
            started_at=datetime.utcnow()
        )
        db_session.add(test_session)
        db_session.commit()
        
        # Create ground truth object
        ground_truth = GroundTruthObject(
            video_id=test_video.id,
            tracking_id="test_vru_1",
            frame_number=100,
            timestamp=3.33,
            class_label="pedestrian",
            x=100.0,
            y=200.0,
            width=60.0,
            height=120.0,
            confidence=0.95,
            validated=True
        )
        db_session.add(ground_truth)
        db_session.commit()
        
        # Create detection event
        detection_event = DetectionEvent(
            test_session_id=test_session.id,
            video_id=test_video.id,
            timestamp=datetime.utcnow(),
            signal_type="GPIO",
            signal_value=1,
            gpio_pin=2,
            validation_result="Pass",
            latency_ms=25.0
        )
        db_session.add(detection_event)
        db_session.commit()
        
        # Create test result
        test_result = TestResult(
            test_session_id=test_session.id,
            total_detections=1,
            passed_detections=1,
            failed_detections=0,
            pass_rate=100.0,
            avg_latency_ms=25.0,
            validation_type="labjack_timing"
        )
        db_session.add(test_result)
        db_session.commit()
        
        # Test relationships
        # Project -> Videos
        assert len(test_project.videos) == 1
        assert test_project.videos[0].id == test_video.id
        
        # Project -> Test Sessions
        assert len(test_project.test_sessions) == 1
        assert test_project.test_sessions[0].id == test_session.id
        
        # Video -> Ground Truth Objects
        assert len(test_video.ground_truth_objects) == 1
        assert test_video.ground_truth_objects[0].id == ground_truth.id
        
        # Test Session -> Project relationship
        assert test_session.project.id == test_project.id
        
        # Ground Truth -> Video relationship
        assert ground_truth.video.id == test_video.id
    
    def test_foreign_key_constraints(self, db_session: Session, test_project):
        """Test foreign key constraints are enforced"""
        # Test invalid project_id in video
        with pytest.raises(IntegrityError):
            invalid_video = Video(
                filename="invalid_video.mp4",
                file_path="/test/invalid_video.mp4",
                file_size=1000000,
                duration=10.0,
                fps=30.0,
                resolution="1920x1080",
                status="validated",
                project_id="non-existent-project-id"
            )
            db_session.add(invalid_video)
            db_session.commit()
        
        db_session.rollback()
        
        # Test invalid test_session_id in detection event
        with pytest.raises(IntegrityError):
            invalid_detection = DetectionEvent(
                test_session_id="non-existent-session-id",
                timestamp=datetime.utcnow(),
                signal_type="GPIO",
                signal_value=1,
                gpio_pin=2
            )
            db_session.add(invalid_detection)
            db_session.commit()
        
        db_session.rollback()
    
    def test_cascade_deletes(self, db_session: Session, test_project, test_video):
        """Test that cascade deletes work correctly"""
        # Create test session with detection events
        test_session = TestSession(
            name="Cascade Test Session",
            project_id=test_project.id,
            status="running",
            started_at=datetime.utcnow()
        )
        db_session.add(test_session)
        db_session.commit()
        
        # Create detection events
        detection_events = []
        for i in range(3):
            detection = DetectionEvent(
                test_session_id=test_session.id,
                timestamp=datetime.utcnow() + timedelta(seconds=i),
                signal_type="GPIO",
                signal_value=1,
                gpio_pin=2
            )
            detection_events.append(detection)
            db_session.add(detection)
        
        # Create ground truth objects
        ground_truth_objects = []
        for i in range(2):
            gt = GroundTruthObject(
                video_id=test_video.id,
                tracking_id=f"cascade_test_vru_{i}",
                frame_number=100 + i * 30,
                timestamp=3.33 + i * 1.0,
                class_label="pedestrian",
                x=100.0 + i * 50,
                y=200.0,
                width=60.0,
                height=120.0,
                confidence=0.95,
                validated=True
            )
            ground_truth_objects.append(gt)
            db_session.add(gt)
        
        db_session.commit()
        
        # Verify objects exist
        assert db_session.execute(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.test_session_id == test_session.id)).scalar() == 3
        assert db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.video_id == test_video.id)).scalar() == 2
        
        # Delete project (should cascade to videos, sessions, detections, ground truth)
        db_session.delete(test_project)
        db_session.commit()
        
        # Verify cascade deletion
        assert db_session.execute(select(func.count()).select_from(Video).where(Video.project_id == test_project.id)).scalar() == 0
        assert db_session.execute(select(func.count()).select_from(TestSession).where(TestSession.project_id == test_project.id)).scalar() == 0
        assert db_session.execute(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.test_session_id == test_session.id)).scalar() == 0
        assert db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.video_id == test_video.id)).scalar() == 0
    
    def test_unique_constraints(self, db_session: Session, test_project):
        """Test unique constraints are enforced"""
        # Test project name uniqueness (if implemented)
        # This would depend on your specific schema constraints
        
        # Test video filename uniqueness within project (if implemented)
        video1 = Video(
            filename="unique_test.mp4",
            file_path="/test/unique_test_1.mp4",
            file_size=1000000,
            duration=10.0,
            fps=30.0,
            resolution="1920x1080",
            status="validated",
            project_id=test_project.id
        )
        db_session.add(video1)
        db_session.commit()
        
        # This should succeed (different path, same filename is typically allowed)
        video2 = Video(
            filename="unique_test.mp4",
            file_path="/test/unique_test_2.mp4",
            file_size=1000000,
            duration=10.0,
            fps=30.0,
            resolution="1920x1080",
            status="validated",
            project_id=test_project.id
        )
        db_session.add(video2)
        db_session.commit()  # Should succeed unless you have filename uniqueness constraint
    
    def test_json_field_storage_and_retrieval(self, db_session: Session, test_project):
        """Test JSON field storage and retrieval"""
        # Test session configuration JSON field
        complex_config = {
            "video_timing": {
                "video_start_unix_time": datetime.utcnow().timestamp(),
                "fps": 60.0,
                "duration_seconds": 120.0,
                "sync_method": "hardware_trigger"
            },
            "ground_truth_matching": {
                "tolerance_ms": 100,
                "enabled": True,
                "algorithm": "closest_temporal",
                "parameters": {
                    "window_size": 200,
                    "confidence_threshold": 0.8
                }
            },
            "test_metadata": {
                "environment": "test",
                "version": "1.0.0",
                "tags": ["integration", "hil", "performance"]
            }
        }
        
        test_session = TestSession(
            name="JSON Test Session",
            project_id=test_project.id,
            status="running",
            started_at=datetime.utcnow(),
            configuration=complex_config
        )
        db_session.add(test_session)
        db_session.commit()
        
        # Retrieve and verify JSON data
        retrieved_session = db_session.execute(select(TestSession).where(TestSession.id == test_session.id)).scalar_one_or_none()
        
        assert retrieved_session.configuration is not None
        assert retrieved_session.configuration["video_timing"]["fps"] == 60.0
        assert retrieved_session.configuration["ground_truth_matching"]["tolerance_ms"] == 100
        assert "integration" in retrieved_session.configuration["test_metadata"]["tags"]
        
        # Test JSON field updates
        retrieved_session.configuration["test_metadata"]["updated"] = True
        retrieved_session.configuration["new_field"] = {"test": "value"}
        db_session.commit()
        
        # Verify updates persisted
        final_session = db_session.execute(select(TestSession).where(TestSession.id == test_session.id)).scalar_one_or_none()
        assert final_session.configuration["test_metadata"]["updated"] is True
        assert final_session.configuration["new_field"]["test"] == "value"
    
    def test_datetime_timezone_handling(self, db_session: Session, test_project):
        """Test datetime timezone handling"""
        # Create timestamps in different formats
        utc_now = datetime.utcnow()
        
        test_session = TestSession(
            name="Timezone Test Session",
            project_id=test_project.id,
            status="running",
            started_at=utc_now,
            created_at=utc_now  # This should be auto-set but we can override
        )
        db_session.add(test_session)
        db_session.commit()
        
        # Create detection event with precise timestamp
        detection_event = DetectionEvent(
            test_session_id=test_session.id,
            timestamp=utc_now + timedelta(milliseconds=500),  # 500ms after session start
            signal_type="GPIO",
            signal_value=1,
            gpio_pin=2
        )
        db_session.add(detection_event)
        db_session.commit()
        
        # Retrieve and verify timestamps
        retrieved_session = db_session.execute(select(TestSession).where(TestSession.id == test_session.id)).scalar_one_or_none()
        retrieved_detection = db_session.execute(select(DetectionEvent).where(DetectionEvent.id == detection_event.id)).scalar_one_or_none()
        
        # Verify timestamp preservation
        assert retrieved_session.started_at.replace(microsecond=0) == utc_now.replace(microsecond=0)
        
        # Calculate time difference
        time_diff = (retrieved_detection.timestamp - retrieved_session.started_at).total_seconds()
        assert abs(time_diff - 0.5) < 0.001  # Should be ~500ms difference
    
    def test_database_indexes_performance(self, db_session: Session, test_project, test_video):
        """Test that database indexes improve query performance"""
        import time
        
        # Create large dataset to test index performance
        ground_truth_objects = []
        for i in range(1000):
            gt = GroundTruthObject(
                video_id=test_video.id,
                tracking_id=f"perf_test_vru_{i}",
                frame_number=i,
                timestamp=i * 0.1,
                class_label="pedestrian" if i % 2 == 0 else "cyclist",
                x=100.0 + (i % 100),
                y=200.0,
                width=60.0,
                height=120.0,
                confidence=0.80 + (i % 20) * 0.01,
                validated=(i % 3 == 0)
            )
            ground_truth_objects.append(gt)
            
            # Batch insert for performance
            if len(ground_truth_objects) >= 100:
                db_session.add_all(ground_truth_objects)
                db_session.commit()
                ground_truth_objects = []
        
        # Insert remaining objects
        if ground_truth_objects:
            db_session.add_all(ground_truth_objects)
            db_session.commit()
        
        # Test indexed queries performance
        queries_to_test = [
            ("video_id index", lambda: db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.video_id == test_video.id)).scalar()),
            ("timestamp index", lambda: db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.timestamp >= 50.0)).scalar()),
            ("class_label index", lambda: db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.class_label == "pedestrian")).scalar()),
            ("confidence index", lambda: db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.confidence >= 0.90)).scalar()),
            ("validated index", lambda: db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.validated == True)).scalar())
        ]
        
        for query_name, query_func in queries_to_test:
            start_time = time.perf_counter()
            result = query_func()
            end_time = time.perf_counter()
            
            query_time = end_time - start_time
            
            # Performance assertion - queries should be fast with proper indexes
            assert query_time < 0.1, f"{query_name} query took {query_time:.3f}s, indexes may not be working"
            assert result > 0, f"{query_name} query returned no results"
            
            print(f"{query_name}: {query_time:.3f}s, {result} results")
    
    def test_transaction_rollback_scenarios(self, db_session: Session, test_project, test_video):
        """Test transaction rollback scenarios"""
        # Test successful transaction
        try:
            test_session = TestSession(
                name="Transaction Test Session",
                project_id=test_project.id,
                status="running",
                started_at=datetime.utcnow()
            )
            db_session.add(test_session)
            
            ground_truth = GroundTruthObject(
                video_id=test_video.id,
                tracking_id="transaction_test_vru",
                frame_number=100,
                timestamp=3.33,
                class_label="pedestrian",
                x=100.0,
                y=200.0,
                width=60.0,
                height=120.0,
                confidence=0.95,
                validated=True
            )
            db_session.add(ground_truth)
            
            db_session.commit()
            
            # Verify objects were created
            assert db_session.execute(select(TestSession).where(TestSession.id == test_session.id)).scalar_one_or_none() is not None
            assert db_session.execute(select(GroundTruthObject).where(GroundTruthObject.id == ground_truth.id)).scalar_one_or_none() is not None
            
        except Exception as e:
            db_session.rollback()
            pytest.fail(f"Successful transaction failed: {e}")
        
        # Test transaction rollback on error
        initial_session_count = db_session.execute(select(func.count()).select_from(TestSession)).scalar()
        initial_gt_count = db_session.execute(select(func.count()).select_from(GroundTruthObject)).scalar()
        
        try:
            # Start transaction
            rollback_session = TestSession(
                name="Rollback Test Session",
                project_id=test_project.id,
                status="running",
                started_at=datetime.utcnow()
            )
            db_session.add(rollback_session)
            
            # Add valid ground truth
            valid_gt = GroundTruthObject(
                video_id=test_video.id,
                tracking_id="rollback_test_vru_1",
                frame_number=200,
                timestamp=6.67,
                class_label="cyclist",
                x=150.0,
                y=250.0,
                width=80.0,
                height=100.0,
                confidence=0.90,
                validated=True
            )
            db_session.add(valid_gt)
            
            # Add invalid ground truth (this should cause an error)
            invalid_gt = GroundTruthObject(
                video_id="non-existent-video-id",  # Invalid foreign key
                tracking_id="rollback_test_vru_2",
                frame_number=300,
                timestamp=10.0,
                class_label="pedestrian",
                x=200.0,
                y=300.0,
                width=60.0,
                height=120.0,
                confidence=0.85,
                validated=True
            )
            db_session.add(invalid_gt)
            
            # This should fail and trigger rollback
            db_session.commit()
            
        except Exception:
            # Expected exception due to foreign key constraint
            db_session.rollback()
            
            # Verify rollback worked - counts should be unchanged
            final_session_count = db_session.execute(select(func.count()).select_from(TestSession)).scalar()
            final_gt_count = db_session.execute(select(func.count()).select_from(GroundTruthObject)).scalar()
            
            assert final_session_count == initial_session_count, "Session count changed after rollback"
            assert final_gt_count == initial_gt_count, "Ground truth count changed after rollback"
    
    def test_concurrent_database_operations(self, db_session: Session, test_project, test_video):
        """Test concurrent database operations"""
        import threading
        import concurrent.futures
        
        # Shared results list
        results = []
        lock = threading.Lock()
        
        def concurrent_database_operation(thread_id):
            """Simulate concurrent database operations"""
            try:
                # Each thread creates its own session (in real implementation)
                # For testing, we'll simulate with shared session but synchronize access
                
                with lock:
                    # Create ground truth object
                    gt = GroundTruthObject(
                        video_id=test_video.id,
                        tracking_id=f"concurrent_test_vru_{thread_id}",
                        frame_number=thread_id * 10,
                        timestamp=thread_id * 1.0,
                        class_label="pedestrian",
                        x=100.0 + thread_id,
                        y=200.0,
                        width=60.0,
                        height=120.0,
                        confidence=0.85,
                        validated=True
                    )
                    db_session.add(gt)
                    db_session.commit()
                    
                    results.append({"thread_id": thread_id, "success": True, "gt_id": gt.id})
                
            except Exception as e:
                with lock:
                    results.append({"thread_id": thread_id, "success": False, "error": str(e)})
        
        # Run concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(concurrent_database_operation, i) for i in range(10)]
            concurrent.futures.wait(futures)
        
        # Verify all operations completed
        assert len(results) == 10
        successful_operations = [r for r in results if r["success"]]
        failed_operations = [r for r in results if not r["success"]]
        
        # Most operations should succeed (exact number depends on database locking behavior)
        assert len(successful_operations) >= 5, f"Too many concurrent operations failed: {len(failed_operations)}"
        
        # Verify created objects exist in database
        created_objects = db_session.execute(
            select(GroundTruthObject).where(
                GroundTruthObject.tracking_id.like("concurrent_test_vru_%")
            )
        ).scalars().all()

        assert len(created_objects) == len(successful_operations)
    
    def test_database_schema_validation(self, db_session: Session):
        """Test database schema matches model definitions"""
        # Test that all expected tables exist
        inspector = db_session.bind.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [row[0] for row in inspector]
        
        expected_tables = [
            "projects", "videos", "test_sessions", "detection_events",
            "test_results", "ground_truth_objects"
        ]
        
        for table in expected_tables:
            assert table in table_names, f"Expected table '{table}' not found in database schema"
        
        # Test column existence for critical tables
        # Projects table
        project_columns = db_session.bind.execute(text("PRAGMA table_info(projects)")).fetchall()
        project_column_names = [col[1] for col in project_columns]
        
        expected_project_columns = ["id", "name", "description", "camera_model", "camera_view", "signal_type", "status"]
        for col in expected_project_columns:
            assert col in project_column_names, f"Expected column '{col}' not found in projects table"
        
        # Videos table
        video_columns = db_session.bind.execute(text("PRAGMA table_info(videos)")).fetchall()
        video_column_names = [col[1] for col in video_columns]
        
        expected_video_columns = ["id", "filename", "file_path", "duration", "fps", "resolution", "project_id", "status"]
        for col in expected_video_columns:
            assert col in video_column_names, f"Expected column '{col}' not found in videos table"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])