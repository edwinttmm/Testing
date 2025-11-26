"""Unit tests for timing quality schema changes - FIX-1, FIX-5"""
import pytest
import uuid
import time
from sqlalchemy.exc import IntegrityError
from models import TestSession, DetectionEvent, Project


class TestTimingQualitySchema:
    """Test database schema changes for timing quality tracking"""

    def test_test_session_has_timing_degraded_field(self, db_session, sample_project_id):
        """Test that TestSession has timing_degraded field with default False"""
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id,
            timing_degraded=False
        )

        db_session.add(session)
        db_session.commit()

        assert hasattr(session, 'timing_degraded')
        assert session.timing_degraded == False

    def test_test_session_timing_degraded_defaults_false(self, db_session, sample_project_id):
        """Test that timing_degraded defaults to False if not specified"""
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id
        )

        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.timing_degraded == False

    def test_test_session_has_timing_verified_field(self, db_session, sample_project_id):
        """Test that TestSession has timing_verified field"""
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id,
            timing_verified=True
        )

        db_session.add(session)
        db_session.commit()

        assert hasattr(session, 'timing_verified')
        assert session.timing_verified == True

    def test_test_session_timing_verified_defaults_true(self, db_session, sample_project_id):
        """Test that timing_verified defaults to True"""
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id
        )

        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.timing_verified == True

    def test_detection_event_has_usable_for_validation_field(self, db_session, sample_session_id):
        """Test that DetectionEvent has usable_for_validation field"""
        detection = DetectionEvent(
            test_session_id=sample_session_id,
            voltage=4.5,
            timestamp=time.time(),
            usable_for_validation=True
        )

        db_session.add(detection)
        db_session.commit()

        assert hasattr(detection, 'usable_for_validation')
        assert detection.usable_for_validation == True

    def test_detection_event_usable_defaults_true(self, db_session, sample_session_id):
        """Test that usable_for_validation defaults to True"""
        detection = DetectionEvent(
            test_session_id=sample_session_id,
            voltage=4.5,
            timestamp=time.time()
        )

        db_session.add(detection)
        db_session.commit()
        db_session.refresh(detection)

        assert detection.usable_for_validation == True

    def test_can_filter_by_timing_quality(self, db_session, sample_project_id):
        """Test that we can query sessions by timing quality"""
        # Create degraded session
        degraded = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id,
            timing_degraded=True,
            timing_verified=False
        )

        # Create clean session
        clean = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id,
            timing_degraded=False,
            timing_verified=True
        )

        db_session.add_all([degraded, clean])
        db_session.commit()

        # Query clean sessions only
        clean_sessions = db_session.execute(select(TestSession).where(
            TestSession.timing_degraded == False,
            TestSession.timing_verified == True
        )).scalars().all()

        assert len(clean_sessions) >= 1
        assert all(not s.timing_degraded for s in clean_sessions)
        assert all(s.timing_verified for s in clean_sessions)

    def test_can_filter_detections_by_quality(self, db_session, sample_session_id):
        """Test that we can query detections by validation usability"""
        # Create usable detection
        usable = DetectionEvent(
            test_session_id=sample_session_id,
            voltage=4.5,
            timestamp=time.time(),
            usable_for_validation=True
        )

        # Create unusable detection
        unusable = DetectionEvent(
            test_session_id=sample_session_id,
            voltage=3.8,
            timestamp=time.time(),
            usable_for_validation=False
        )

        db_session.add_all([usable, unusable])
        db_session.commit()

        # Query usable detections only
        usable_detections = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == sample_session_id,
            DetectionEvent.usable_for_validation == True
        )).scalars().all()

        assert len(usable_detections) == 1
        assert usable_detections[0].voltage == 4.5

    def test_timing_fields_persist_across_commits(self, db_session, sample_project_id):
        """Test that timing quality fields persist correctly"""
        session_id = str(uuid.uuid4())

        # Create and commit
        session = TestSession(
            id=session_id,
            project_id=sample_project_id,
            timing_degraded=True,
            timing_verified=False
        )
        db_session.add(session)
        db_session.commit()

        # Clear session and re-query
        db_session.expunge_all()
        found = db_session.execute(select(TestSession).where(
            TestSession.id == session_id
        )).scalar_one_or_none()

        assert found is not None
        assert found.timing_degraded == True
        assert found.timing_verified == False

    def test_can_update_timing_fields(self, db_session, sample_project_id):
        """Test that timing fields can be updated"""
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id,
            timing_degraded=False,
            timing_verified=True
        )
        db_session.add(session)
        db_session.commit()

        # Update fields
        session.timing_degraded = True
        session.timing_verified = False
        db_session.commit()

        # Verify update
        db_session.refresh(session)
        assert session.timing_degraded == True
        assert session.timing_verified == False
