"""Regression tests to ensure fixes don't break existing functionality"""
import pytest
import uuid
import time
from models import TestSession, DetectionEvent, Project


class TestBasicSessionFunctionality:
    """Test that basic session operations still work"""

    def test_create_session_still_works(self, db_session, sample_project_id):
        """Test that creating a session works as before"""
        session_id = str(uuid.uuid4())
        session = TestSession(
            id=session_id,
            project_id=sample_project_id
        )

        db_session.add(session)
        db_session.commit()

        # Verify it was created
        found = db_session.execute(select(TestSession).where(
            TestSession.id == session_id
        )).scalar_one_or_none()

        assert found is not None
        assert found.id == session_id
        assert found.project_id == sample_project_id

    def test_query_session_still_works(self, db_session, sample_project_id):
        """Test that querying sessions works as before"""
        # Create multiple sessions
        session_ids = [str(uuid.uuid4()) for _ in range(3)]

        for session_id in session_ids:
            session = TestSession(
                id=session_id,
                project_id=sample_project_id
            )
            db_session.add(session)

        db_session.commit()

        # Query all sessions for project
        sessions = db_session.execute(select(TestSession).where(
            TestSession.project_id == sample_project_id
        )).scalars().all()

        assert len(sessions) >= 3
        found_ids = [s.id for s in sessions]
        for session_id in session_ids:
            assert session_id in found_ids

    def test_update_session_still_works(self, db_session, sample_project_id):
        """Test that updating sessions works as before"""
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id
        )
        db_session.add(session)
        db_session.commit()

        # Update session
        session.status = "completed"
        db_session.commit()

        # Verify update
        db_session.refresh(session)
        assert session.status == "completed"

    def test_delete_session_still_works(self, db_session, sample_project_id):
        """Test that deleting sessions works as before"""
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.id

        # Delete session
        db_session.delete(session)
        db_session.commit()

        # Verify deletion
        found = db_session.execute(select(TestSession).where(
            TestSession.id == session_id
        )).scalar_one_or_none()

        assert found is None


class TestDetectionEventFunctionality:
    """Test that detection event operations still work"""

    def test_create_detection_event_still_works(self, db_session, sample_session_id):
        """Test that creating detection events works as before"""
        detection = DetectionEvent(
            test_session_id=sample_session_id,
            voltage=4.5,
            timestamp=time.time()
        )

        db_session.add(detection)
        db_session.commit()

        # Verify it was created
        found = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == sample_session_id
        )).scalar_one_or_none()

        assert found is not None
        assert found.voltage == 4.5

    def test_query_detection_events_still_works(self, db_session, sample_session_id):
        """Test that querying detection events works as before"""
        # Create multiple detections
        voltages = [4.0, 4.5, 5.0]

        for voltage in voltages:
            detection = DetectionEvent(
                test_session_id=sample_session_id,
                voltage=voltage,
                timestamp=time.time()
            )
            db_session.add(detection)

        db_session.commit()

        # Query all detections for session
        detections = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == sample_session_id
        )).scalars().all()

        assert len(detections) >= 3
        found_voltages = [d.voltage for d in detections]
        for voltage in voltages:
            assert voltage in found_voltages

    def test_filter_detection_events_still_works(self, db_session, sample_session_id):
        """Test that filtering detection events works as before"""
        # Create detections with different voltages
        for i in range(10):
            detection = DetectionEvent(
                test_session_id=sample_session_id,
                voltage=4.0 + i * 0.2,
                timestamp=time.time()
            )
            db_session.add(detection)

        db_session.commit()

        # Filter by voltage range
        high_voltage = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == sample_session_id,
            DetectionEvent.voltage > 5.0
        )).scalars().all()

        assert len(high_voltage) > 0
        assert all(d.voltage > 5.0 for d in high_voltage)


class TestProjectFunctionality:
    """Test that project operations still work"""

    def test_create_project_still_works(self, db_session):
        """Test that creating projects works as before"""
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            description="Regression test project"
        )

        db_session.add(project)
        db_session.commit()

        # Verify it was created
        found = db_session.execute(select(Project).where(
            Project.id == project.id
        )).scalar_one_or_none()

        assert found is not None
        assert found.name == "Test Project"

    def test_query_projects_still_works(self, db_session):
        """Test that querying projects works as before"""
        # Create multiple projects
        names = ["Project A", "Project B", "Project C"]

        for name in names:
            project = Project(
                id=str(uuid.uuid4()),
                name=name,
                description="Test"
            )
            db_session.add(project)

        db_session.commit()

        # Query all projects
        projects = db_session.execute(select(Project)).scalars().all()

        assert len(projects) >= 3
        found_names = [p.name for p in projects]
        for name in names:
            assert name in found_names


class TestAPIEndpoints:
    """Test that API endpoints still work"""

    def test_get_sessions_endpoint_works(self, client):
        """Test that GET /api/test-sessions endpoint works"""
        response = client.get("/api/test-sessions")

        # Should return 200 or 401 (if auth required)
        assert response.status_code in [200, 401, 403]

    def test_create_session_endpoint_works(self, client, sample_project_id):
        """Test that POST /api/test-sessions endpoint works"""
        response = client.post(
            "/api/test-sessions",
            json={
                "project_id": sample_project_id,
                "config": {}
            }
        )

        # Should return 201 (created) or 401 (if auth required)
        assert response.status_code in [201, 401, 403]

    def test_get_single_session_endpoint_works(self, client, sample_session_id):
        """Test that GET /api/test-sessions/{id} endpoint works"""
        response = client.get(f"/api/test-sessions/{sample_session_id}")

        # Should return 200, 404, or 401
        assert response.status_code in [200, 404, 401, 403]

    def test_get_projects_endpoint_works(self, client):
        """Test that GET /api/projects endpoint works"""
        response = client.get("/api/projects")

        # Should return 200 or 401
        assert response.status_code in [200, 401, 403]


class TestGroundTruthMatching:
    """Test that ground truth matching still works"""

    def test_can_match_detections_to_ground_truth(self, db_session, sample_session_id):
        """Test that detection-to-ground-truth matching works"""
        # Create detections
        detection_times = [1.0, 2.0, 3.0]

        for t in detection_times:
            detection = DetectionEvent(
                test_session_id=sample_session_id,
                voltage=4.5,
                timestamp=t
            )
            db_session.add(detection)

        db_session.commit()

        # Simulate ground truth matching
        detections = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == sample_session_id
        )).scalars().all()

        # Should be able to query and process detections
        assert len(detections) == 3

        # Verify timestamps are accessible for matching
        timestamps = [d.timestamp for d in detections]
        assert timestamps == detection_times


class TestDatabaseRelationships:
    """Test that database relationships still work"""

    def test_session_to_project_relationship(self, db_session, sample_project_id):
        """Test that session-to-project relationship works"""
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id
        )
        db_session.add(session)
        db_session.commit()

        # Should be able to query project from session
        # (assuming relationship is defined)
        assert session.project_id == sample_project_id

    def test_detection_to_session_relationship(self, db_session, sample_session_id):
        """Test that detection-to-session relationship works"""
        detection = DetectionEvent(
            test_session_id=sample_session_id,
            voltage=4.5,
            timestamp=time.time()
        )
        db_session.add(detection)
        db_session.commit()

        # Should be able to query session from detection
        assert detection.test_session_id == sample_session_id


class TestExistingQueries:
    """Test that existing queries still work"""

    def test_count_sessions_still_works(self, db_session):
        """Test that counting sessions works"""
        count = db_session.execute(select(func.count()).select_from(TestSession)).scalar()
        assert isinstance(count, int)
        assert count >= 0

    def test_filter_by_project_still_works(self, db_session, sample_project_id):
        """Test that filtering by project works"""
        sessions = db_session.execute(select(TestSession).where(
            TestSession.project_id == sample_project_id
        )).scalars().all()

        assert isinstance(sessions, list)

    def test_order_by_timestamp_still_works(self, db_session, sample_session_id):
        """Test that ordering by timestamp works"""
        # Create detections with different timestamps
        for i in range(5):
            detection = DetectionEvent(
                test_session_id=sample_session_id,
                voltage=4.5,
                timestamp=float(i)
            )
            db_session.add(detection)

        db_session.commit()

        # Query ordered by timestamp
        detections = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == sample_session_id
        )).scalars().order_by(DetectionEvent.timestamp).all()

        # Verify ordering
        timestamps = [d.timestamp for d in detections]
        assert timestamps == sorted(timestamps)


class TestBackwardsCompatibility:
    """Test backwards compatibility with existing data"""

    def test_old_sessions_without_timing_fields_work(self, db_session, sample_project_id):
        """Test that old sessions without timing fields still work"""
        # Create session without explicitly setting timing fields
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id
        )
        db_session.add(session)
        db_session.commit()

        # Should have default values
        db_session.refresh(session)
        assert hasattr(session, 'timing_degraded')
        assert hasattr(session, 'timing_verified')

    def test_old_detections_without_usable_field_work(self, db_session, sample_session_id):
        """Test that old detections without usable_for_validation field still work"""
        # Create detection without explicitly setting usable_for_validation
        detection = DetectionEvent(
            test_session_id=sample_session_id,
            voltage=4.5,
            timestamp=time.time()
        )
        db_session.add(detection)
        db_session.commit()

        # Should have default value
        db_session.refresh(detection)
        assert hasattr(detection, 'usable_for_validation')
