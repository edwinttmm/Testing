"""
Database Schema Integrity Tests for Hybrid LabJack System

This test suite validates:
1. Existing database schema remains unchanged
2. New fields are purely additive and nullable
3. Legacy queries continue to work
4. Performance characteristics unchanged
5. Data migration paths are safe
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db, engine
from models import (
    TestSession, DetectionEvent, Project, Video, GroundTruthObject,
    AuthUser, UserSession
)


class TestDatabaseSchemaIntegrity:
    """Comprehensive database schema integrity validation"""
    
    @pytest.fixture
    def db_session(self):
        """Database session fixture"""
        db = next(get_db())
        try:
            yield db
        finally:
            db.close()
    
    def test_legacy_tables_exist(self, db_session):
        """Test that all legacy tables still exist"""
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        required_legacy_tables = [
            "projects",
            "videos", 
            "test_sessions",
            "detection_events",
            "ground_truth_objects",
            "auth_users",
            "user_sessions"
        ]
        
        for table in required_legacy_tables:
            assert table in existing_tables, f"Required legacy table '{table}' is missing"

    def test_detection_events_schema_integrity(self, db_session):
        """Test that detection_events table maintains backward compatibility"""
        inspector = inspect(engine)
        columns = inspector.get_columns("detection_events")
        column_info = {col["name"]: col for col in columns}
        
        # Essential legacy columns that must exist
        legacy_columns = {
            "id": {"type": "VARCHAR", "nullable": False, "primary_key": True},
            "test_session_id": {"type": "VARCHAR", "nullable": False},
            "timestamp": {"type": "FLOAT", "nullable": True},
            "frame_number": {"type": "INTEGER", "nullable": True},
            "actual_latency_ms": {"type": "FLOAT", "nullable": True},
            "processing_time_ms": {"type": "FLOAT", "nullable": True},
            "voltage_level": {"type": "FLOAT", "nullable": True},
            "labjack_voltage": {"type": "FLOAT", "nullable": True},
            "labjack_timestamp": {"type": "FLOAT", "nullable": True},
            "detection_channel": {"type": "VARCHAR", "nullable": True},
            "validation_result": {"type": "VARCHAR", "nullable": True}
        }
        
        for col_name, expected_props in legacy_columns.items():
            assert col_name in column_info, f"Legacy column '{col_name}' missing from detection_events"
            
            col = column_info[col_name]
            
            # Check nullability - legacy columns should maintain their original nullability
            if not expected_props.get("primary_key", False):
                expected_nullable = expected_props.get("nullable", True)
                actual_nullable = col["nullable"]
                assert actual_nullable == expected_nullable, f"Column '{col_name}' nullability changed: expected {expected_nullable}, got {actual_nullable}"
        
        # New hybrid logging columns should be nullable (additive only)
        new_hybrid_columns = [
            "video_relative_timestamp",
            "video_frame_number", 
            "timing_sync_quality",
            "raw_voltage_data",
            "raw_timing_data",
            "screenshot_path",
            "screenshot_zoom_path"
        ]
        
        for col_name in new_hybrid_columns:
            if col_name in column_info:
                col = column_info[col_name]
                assert col["nullable"] == True, f"New hybrid column '{col_name}' should be nullable for backward compatibility"

    def test_test_sessions_schema_integrity(self, db_session):
        """Test that test_sessions table maintains backward compatibility"""
        inspector = inspect(engine)
        columns = inspector.get_columns("test_sessions")
        column_info = {col["name"]: col for col in columns}
        
        # Core legacy columns for test sessions
        legacy_columns = {
            "id", "name", "project_id", "status", "started_at", 
            "completed_at", "max_latency_ms", "labjack_connected"
        }
        
        for col_name in legacy_columns:
            assert col_name in column_info, f"Legacy column '{col_name}' missing from test_sessions"
        
        # Enhanced timing fields should be nullable additions
        enhanced_timing_fields = [
            "video_playback_start_time", "video_timing_sync_status",
            "timing_accuracy_ns", "command_start_timestamp",
            "presentation_delay_ms", "presentation_delay_quality"
        ]
        
        for col_name in enhanced_timing_fields:
            if col_name in column_info:
                col = column_info[col_name]
                assert col["nullable"] == True, f"Enhanced timing field '{col_name}' should be nullable"

    def test_legacy_queries_continue_working(self, db_session):
        """Test that legacy database queries continue to work unchanged"""
        
        # Create test project
        project = Project(
            name="Legacy Query Test Project",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active"
        )
        db_session.add(project)
        db_session.commit()
        
        # Create test video
        video = Video(
            filename="test_video.mp4",
            file_path="/test/path/test_video.mp4",
            duration=30.0,
            fps=30.0,
            project_id=project.id,
            status="uploaded"
        )
        db_session.add(video)
        db_session.commit()
        
        # Create legacy test session
        test_session = TestSession(
            name="Legacy Query Test Session",
            project_id=project.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            max_latency_ms=100,
            labjack_connected=True,
            video_id=video.id
        )
        db_session.add(test_session)
        db_session.commit()
        
        # Create legacy detection events
        detection_events = []
        for i in range(5):
            event = DetectionEvent(
                test_session_id=test_session.id,
                timestamp=time.time() + i,
                frame_number=i * 10,
                actual_latency_ms=75.0 + i * 5,
                processing_time_ms=45.0 + i * 2,
                voltage_level=3.0 + i * 0.1,
                labjack_voltage=3.0 + i * 0.1,
                labjack_timestamp=time.time() + i,
                detection_channel="AIN0",
                validation_result="pass" if i < 4 else "fail"
            )
            detection_events.append(event)
            db_session.add(event)
        
        db_session.commit()
        
        # Test legacy query patterns
        
        # 1. Basic session query
        session_query = db_session.query(TestSession).filter(
            TestSession.id == test_session.id
        ).first()
        assert session_query is not None
        assert session_query.name == "Legacy Query Test Session"
        
        # 2. Detection events for session
        events_query = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == test_session.id
        ).all()
        assert len(events_query) == 5
        
        # 3. Pass/fail statistics
        pass_count = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == test_session.id,
            DetectionEvent.validation_result == "pass"
        ).count()
        assert pass_count == 4
        
        # 4. Average latency calculation
        avg_latency = db_session.query(
            db_session.query(DetectionEvent.actual_latency_ms).filter(
                DetectionEvent.test_session_id == test_session.id
            ).subquery()
        ).scalar()
        
        # 5. Project-session join
        project_sessions = db_session.query(TestSession, Project).join(
            Project, TestSession.project_id == Project.id
        ).filter(Project.id == project.id).all()
        assert len(project_sessions) == 1
        
        # 6. Video metadata access
        session_video = db_session.query(TestSession, Video).join(
            Video, TestSession.video_id == Video.id
        ).filter(TestSession.id == test_session.id).first()
        assert session_video is not None
        assert session_video[1].filename == "test_video.mp4"

    def test_raw_sql_query_compatibility(self, db_session):
        """Test that raw SQL queries used by the application continue to work"""
        
        # Test queries used in enhanced HIL results endpoint
        session_query = text("""
            SELECT ts.id, ts.name, ts.project_id, ts.video_id, ts.status, ts.started_at, ts.completed_at,
                   ts.tolerance_ms, ts.session_type, ts.video_playback_start_time,
                   ts.video_timing_sync_status, ts.timing_accuracy_ns,
                   v.fps, v.duration, v.filename
            FROM test_sessions ts
            LEFT JOIN videos v ON ts.video_id = v.id
            WHERE ts.id = :session_id
        """)
        
        # Should execute without error even if no results
        result = db_session.execute(session_query, {"session_id": "non-existent"})
        assert result is not None
        
        # Test detection events raw query
        detection_query = text("""
            SELECT id, test_session_id, frame_number, timestamp, actual_latency_ms, latency_ns,
                   processing_time_ms, voltage_level, labjack_voltage, labjack_timestamp,
                   detection_channel, validation_result, confidence, class_label, vru_type,
                   created_at, video_relative_timestamp, video_frame_number
            FROM detection_events 
            WHERE test_session_id = :session_id
            ORDER BY timestamp ASC
        """)
        
        result = db_session.execute(detection_query, {"session_id": "non-existent"})
        assert result is not None

    def test_index_performance_unchanged(self, db_session):
        """Test that database index performance characteristics remain unchanged"""
        
        # Create test data for performance testing
        project = Project(
            name="Performance Test Project",
            camera_model="Test Camera", 
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        
        # Create multiple test sessions
        sessions = []
        for i in range(20):
            session = TestSession(
                name=f"Performance Test Session {i}",
                project_id=project.id,
                status="completed",
                started_at=datetime.now(timezone.utc) - timedelta(hours=i),
                max_latency_ms=100,
                labjack_connected=True
            )
            sessions.append(session)
            db_session.add(session)
        
        db_session.commit()
        
        # Create many detection events
        for session in sessions[:5]:  # Just first 5 sessions to keep test reasonable
            for j in range(100):
                event = DetectionEvent(
                    test_session_id=session.id,
                    timestamp=time.time() + j,
                    frame_number=j,
                    actual_latency_ms=75.0,
                    validation_result="pass"
                )
                db_session.add(event)
        
        db_session.commit()
        
        # Performance tests - queries should complete quickly
        
        # 1. Session lookup by ID (should use primary key index)
        start_time = time.time()
        session = db_session.query(TestSession).filter(
            TestSession.id == sessions[0].id
        ).first()
        query_time = time.time() - start_time
        assert query_time < 0.1  # Should be very fast (< 100ms)
        assert session is not None
        
        # 2. Sessions by project (should use foreign key index)
        start_time = time.time()
        project_sessions = db_session.query(TestSession).filter(
            TestSession.project_id == project.id
        ).all()
        query_time = time.time() - start_time
        assert query_time < 0.2  # Should be reasonably fast (< 200ms)
        assert len(project_sessions) == 20
        
        # 3. Detection events by session (should use foreign key index)
        start_time = time.time()
        session_events = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == sessions[0].id
        ).count()
        query_time = time.time() - start_time
        assert query_time < 0.2  # Should be reasonably fast
        assert session_events == 100

    def test_data_type_compatibility(self, db_session):
        """Test that data types remain compatible with existing code"""
        
        # Create test session with various data types
        session = TestSession(
            name="Data Type Test Session",
            project_id=1,  # Integer
            status="completed",  # String
            started_at=datetime.now(timezone.utc),  # DateTime
            max_latency_ms=100,  # Integer
            labjack_connected=True,  # Boolean
            tolerance_ms=100.5  # Float (if field exists)
        )
        db_session.add(session)
        db_session.commit()
        
        # Create detection event with various data types
        event = DetectionEvent(
            test_session_id=session.id,  # String (UUID)
            timestamp=time.time(),  # Float
            frame_number=42,  # Integer
            actual_latency_ms=75.5,  # Float
            processing_time_ms=45.2,  # Float
            voltage_level=3.14159,  # Float with precision
            labjack_voltage=3.2,  # Float
            validation_result="pass"  # String
        )
        db_session.add(event)
        db_session.commit()
        
        # Retrieve and verify data types are preserved
        retrieved_session = db_session.query(TestSession).filter(
            TestSession.id == session.id
        ).first()
        
        assert isinstance(retrieved_session.project_id, int)
        assert isinstance(retrieved_session.name, str)
        assert isinstance(retrieved_session.labjack_connected, bool)
        assert isinstance(retrieved_session.started_at, datetime)
        
        retrieved_event = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).first()
        
        assert isinstance(retrieved_event.timestamp, float)
        assert isinstance(retrieved_event.frame_number, int)
        assert isinstance(retrieved_event.actual_latency_ms, float)
        assert abs(retrieved_event.voltage_level - 3.14159) < 0.00001  # Float precision

    def test_constraint_integrity(self, db_session):
        """Test that database constraints remain intact"""
        
        # Test foreign key constraints
        with pytest.raises(SQLAlchemyError):
            # Should fail due to foreign key constraint
            invalid_session = TestSession(
                name="Invalid Session",
                project_id="non-existent-project-id",
                status="running"
            )
            db_session.add(invalid_session)
            db_session.commit()
        
        db_session.rollback()
        
        # Test NOT NULL constraints on required fields
        with pytest.raises(SQLAlchemyError):
            # Should fail due to missing required field
            invalid_project = Project(
                # Missing required fields like name, camera_model, etc.
                description="Project without required fields"
            )
            db_session.add(invalid_project)
            db_session.commit()
        
        db_session.rollback()

    def test_cascade_behavior_unchanged(self, db_session):
        """Test that cascade delete behavior remains unchanged"""
        
        # Create project with related data
        project = Project(
            name="Cascade Test Project",
            camera_model="Test Camera",
            camera_view="Front-facing VRU", 
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        
        # Create video
        video = Video(
            filename="cascade_test.mp4",
            file_path="/test/cascade_test.mp4",
            project_id=project.id
        )
        db_session.add(video)
        db_session.commit()
        
        # Create test session
        session = TestSession(
            name="Cascade Test Session",
            project_id=project.id,
            video_id=video.id,
            status="completed"
        )
        db_session.add(session)
        db_session.commit()
        
        # Create detection events
        event = DetectionEvent(
            test_session_id=session.id,
            timestamp=time.time(),
            validation_result="pass"
        )
        db_session.add(event)
        db_session.commit()
        
        # Store IDs for verification
        project_id = project.id
        video_id = video.id
        session_id = session.id
        event_id = event.id
        
        # Delete project should cascade to related records
        db_session.delete(project)
        db_session.commit()
        
        # Verify cascade behavior
        assert db_session.query(Project).filter(Project.id == project_id).first() is None
        assert db_session.query(Video).filter(Video.id == video_id).first() is None
        assert db_session.query(TestSession).filter(TestSession.id == session_id).first() is None
        assert db_session.query(DetectionEvent).filter(DetectionEvent.id == event_id).first() is None

    def test_database_migrations_safe(self, db_session):
        """Test that any schema changes are safe and don't break existing data"""
        
        # Create data with legacy structure
        project = Project(
            name="Migration Safety Test",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        
        session = TestSession(
            name="Migration Test Session",
            project_id=project.id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            max_latency_ms=100,
            labjack_connected=True
        )
        db_session.add(session)
        db_session.commit()
        
        # Legacy detection event (without new hybrid fields)
        legacy_event = DetectionEvent(
            test_session_id=session.id,
            timestamp=time.time(),
            frame_number=10,
            actual_latency_ms=75.5,
            processing_time_ms=45.2,
            voltage_level=3.2,
            validation_result="pass"
        )
        db_session.add(legacy_event)
        db_session.commit()
        
        # Verify legacy data can coexist with enhanced data
        enhanced_event = DetectionEvent(
            test_session_id=session.id,
            timestamp=time.time() + 1,
            frame_number=15,
            actual_latency_ms=82.1,
            processing_time_ms=52.7,
            voltage_level=3.1,
            validation_result="pass",
            # Enhanced fields (if they exist)
        )
        
        # Try to set enhanced fields if they exist on the model
        if hasattr(enhanced_event, 'video_relative_timestamp'):
            enhanced_event.video_relative_timestamp = 1.5
        if hasattr(enhanced_event, 'timing_sync_quality'):
            enhanced_event.timing_sync_quality = "high"
        
        db_session.add(enhanced_event)
        db_session.commit()
        
        # Both events should be retrievable and functional
        all_events = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id
        ).all()
        
        assert len(all_events) == 2
        
        # Legacy event should have NULL/None for enhanced fields
        legacy = next(e for e in all_events if e.frame_number == 10)
        assert legacy.actual_latency_ms == 75.5  # Legacy field works
        assert getattr(legacy, 'video_relative_timestamp', None) is None  # Enhanced field is None
        
        # Enhanced event should have values for enhanced fields
        enhanced = next(e for e in all_events if e.frame_number == 15)
        assert enhanced.actual_latency_ms == 82.1  # Legacy field works
        # Enhanced fields may or may not exist depending on current schema


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])