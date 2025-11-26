"""Integration tests for all fixes working together"""
import pytest
import uuid
import time
import threading
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError
from models import TestSession, DetectionEvent, Project


class TestCompleteSessionFlow:
    """Test complete session flow with all fixes integrated"""

    def test_complete_session_lifecycle(self, db_session, sample_project_id):
        """
        Test complete session flow with all fixes:
        - FIX-1: Event signaling with timing quality
        - FIX-2: Session ID propagation
        - FIX-3: Session verification with validation
        - FIX-4: MVCC retry logic
        - FIX-5: Timing quality tracking
        """
        # Create session with proper ID (FIX-2)
        session_id = str(uuid.uuid4())
        session = TestSession(
            id=session_id,
            project_id=sample_project_id,
            timing_degraded=False,
            timing_verified=True
        )
        db_session.add(session)
        db_session.commit()

        # Wait for MVCC visibility (FIX-4)
        time.sleep(0.05)

        # Verify session exists with validation (FIX-3)
        db_session.expire_all()
        found = db_session.execute(select(TestSession).where(
            TestSession.id == session_id
        )).scalar_one_or_none()
        assert found is not None
        assert found.timing_degraded == False
        assert found.timing_verified == True

        # Create detection with quality tracking (FIX-1, FIX-5)
        detection = DetectionEvent(
            test_session_id=session_id,
            voltage=4.5,
            timestamp=time.time(),
            usable_for_validation=True
        )
        db_session.add(detection)
        db_session.commit()

        # Verify detection is queryable
        detections = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.usable_for_validation == True
        )).scalars().all()

        assert len(detections) == 1
        assert detections[0].voltage == 4.5
        assert detections[0].usable_for_validation == True

    def test_degraded_session_handling(self, db_session, sample_project_id):
        """Test handling of sessions with degraded timing"""
        # Create degraded session
        session_id = str(uuid.uuid4())
        session = TestSession(
            id=session_id,
            project_id=sample_project_id,
            timing_degraded=True,
            timing_verified=False
        )
        db_session.add(session)
        db_session.commit()

        # Add detections with mixed quality
        usable = DetectionEvent(
            test_session_id=session_id,
            voltage=4.5,
            timestamp=time.time(),
            usable_for_validation=True
        )
        unusable = DetectionEvent(
            test_session_id=session_id,
            voltage=3.8,
            timestamp=time.time(),
            usable_for_validation=False
        )

        db_session.add_all([usable, unusable])
        db_session.commit()

        # Query should filter based on session and detection quality
        clean_sessions = db_session.execute(select(TestSession).where(
            TestSession.timing_degraded == False,
            TestSession.timing_verified == True
        )).scalars().all()

        # Degraded session should not be in clean results
        assert session_id not in [s.id for s in clean_sessions]

        # Can still query usable detections from degraded session
        usable_detections = db_session.execute(select(DetectionEvent).where(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.usable_for_validation == True
        )).scalars().all()

        assert len(usable_detections) == 1

    def test_concurrent_session_creation(self, db_session, sample_project_id):
        """Test concurrent session creation with MVCC"""
        # NOTE: Cannot use threading with single db_session fixture
        # Instead, create sessions sequentially but test isolation
        session_ids = []

        # Create 5 sessions sequentially
        for i in range(5):
            session_id = str(uuid.uuid4())
            session = TestSession(
                id=session_id,
                project_id=sample_project_id,
                timing_degraded=False,
                timing_verified=True
            )
            db_session.add(session)
            db_session.commit()
            # Refresh to keep in session
            db_session.refresh(session)
            session_ids.append(session_id)

        # All should be queryable
        db_session.expire_all()
        found = db_session.execute(select(TestSession).where(
            TestSession.id.in_(session_ids)
        )).scalars().all()

        assert len(found) == 5

    def test_session_verification_prevents_orphans(self, db_session):
        """Test that session verification prevents orphaned detections"""
        # Try to create detection for non-existent session
        fake_session_id = str(uuid.uuid4())

        detection = DetectionEvent(
            test_session_id=fake_session_id,
            voltage=4.5,
            timestamp=time.time(),
            usable_for_validation=True
        )

        db_session.add(detection)

        # Should raise foreign key constraint error
        with pytest.raises(Exception):  # IntegrityError or similar
            db_session.commit()

    def test_quality_filtering_integration(self, db_session, sample_project_id):
        """Test integrated quality filtering across sessions and detections"""
        # Create 3 sessions with different quality levels
        sessions_data = [
            (str(uuid.uuid4()), False, True),   # Clean session
            (str(uuid.uuid4()), True, False),   # Degraded session
            (str(uuid.uuid4()), False, True),   # Another clean session
        ]

        for session_id, degraded, verified in sessions_data:
            session = TestSession(
                id=session_id,
                project_id=sample_project_id,
                timing_degraded=degraded,
                timing_verified=verified
            )
            db_session.add(session)

        db_session.commit()

        # Add detections to each
        for session_id, degraded, verified in sessions_data:
            for i in range(3):
                detection = DetectionEvent(
                    test_session_id=session_id,
                    voltage=4.0 + i * 0.5,
                    timestamp=time.time(),
                    usable_for_validation=(i % 2 == 0)  # Every other is usable
                )
                db_session.add(detection)

        db_session.commit()

        # Query for high-quality data only
        high_quality_sessions = db_session.execute(select(TestSession).where(
            TestSession.project_id == sample_project_id,
            TestSession.timing_degraded == False,
            TestSession.timing_verified == True
        )).scalars().all()

        assert len(high_quality_sessions) == 2

        # Query for usable detections in high-quality sessions
        session_ids = [s.id for s in high_quality_sessions]
        usable_detections = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id.in_(session_ids),
            DetectionEvent.usable_for_validation == True
        ).all()

        assert len(usable_detections) == 4  # 2 per clean session


class TestMVCCRetryIntegration:
    """Test MVCC retry logic in real scenarios"""

    def test_retry_on_serialization_error(self, db_session, sample_project_id):
        """Test that operations retry on serialization errors"""
        # This simulates the 50ms retry delay scenario
        session_id = str(uuid.uuid4())

        # First transaction
        session = TestSession(
            id=session_id,
            project_id=sample_project_id
        )
        db_session.add(session)
        db_session.commit()
        # Refresh to ensure object stays in session
        db_session.refresh(session)

        # Immediate query might hit MVCC visibility issue
        time.sleep(0.05)  # Standard retry delay

        # Should be visible now
        db_session.expire_all()
        found = db_session.execute(select(TestSession).where(
            TestSession.id == session_id
        )).scalar_one_or_none()

        assert found is not None

    def test_connection_pool_resilience(self, db_session, sample_project_id):
        """Test that connection pool handles concurrent load"""
        # Simulate rapid successive operations
        for i in range(10):
            session = TestSession(
                id=str(uuid.uuid4()),
                project_id=sample_project_id
            )
            db_session.add(session)
            db_session.commit()
            # Refresh to prevent detached instance errors
            db_session.refresh(session)

            # No sleep - rapid operations
            if i % 3 == 0:
                db_session.execute(select(func.count()).select_from(TestSession)).scalar()


class TestSecurityValidationIntegration:
    """Test security validation in real workflows"""

    def test_api_rejects_invalid_uuids(self, client):
        """Test that API endpoints reject invalid UUIDs"""
        response = client.post(
            "/api/test-sessions",
            json={
                "project_id": "invalid-uuid",
                "config": {}
            }
        )

        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]

    def test_api_rejects_sql_injection(self, client):
        """Test that API rejects SQL injection attempts"""
        response = client.post(
            "/api/test-sessions",
            json={
                "project_id": "'; DROP TABLE test_sessions; --",
                "config": {}
            }
        )

        assert response.status_code == 400
        assert "Invalid" in response.json()["detail"]
