"""
Integration Tests for Quality Tracking System

Tests the complete end-to-end flow of quality tracking:
1. Detection creation with quality flags
2. Quality warning generation
3. Quality API endpoints
4. Quality filtering in results
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime

import sys
sys.path.insert(0, '/home/rigade/Testing/ai-model-validation-platform/backend')

from main import app
from database import SessionLocal, engine
from models import TestSession, DetectionEvent, Base


@pytest.fixture(scope="module")
def test_client():
    """Create test client for API testing"""
    client = TestClient(app)
    return client


@pytest.fixture(scope="function")
def db_session():
    """Create fresh database session for each test"""
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session
    session = SessionLocal()
    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


class TestQualityTrackingEndToEnd:
    """Test complete quality tracking workflow"""

    def test_complete_quality_tracking_flow(self, test_client, db_session):
        """
        Test complete flow:
        1. Create test session
        2. Create detections with quality flags
        3. Retrieve quality warnings
        4. Filter by quality
        """
        # Step 1: Create test session
        session_id = str(uuid4())
        test_session = TestSession(
            id=session_id,
            project_id=str(uuid4()),
            video_sequence_id=str(uuid4()),
            status="completed",
            timing_degraded=True  # Mark session as having timing issues
        )
        db_session.add(test_session)
        db_session.commit()

        # Step 2: Create detections with mixed quality
        # 70 good detections
        for i in range(70):
            detection = DetectionEvent(
                id=str(uuid4()),
                test_session_id=session_id,
                video_id=str(uuid4()),
                frame_number=i,
                timestamp=datetime.utcnow(),
                usable_for_validation=True,  # Good quality
                timing_degraded=False
            )
            db_session.add(detection)

        # 30 degraded detections
        for i in range(70, 100):
            detection = DetectionEvent(
                id=str(uuid4()),
                test_session_id=session_id,
                video_id=str(uuid4()),
                frame_number=i,
                timestamp=datetime.utcnow(),
                usable_for_validation=False,  # Degraded quality
                timing_degraded=True
            )
            db_session.add(detection)

        db_session.commit()

        # Step 3: Check quality warnings via API
        response = test_client.get(f"/api/quality/warnings/{session_id}")

        assert response.status_code == 200
        warnings = response.json()

        # Should have warnings about degraded detections
        assert len(warnings) > 0
        assert any(w['code'] == 'SESSION_TIMING_DEGRADED' for w in warnings)

        # Step 4: Get quality statistics
        response = test_client.get(f"/api/quality/statistics/{session_id}")

        assert response.status_code == 200
        stats = response.json()

        assert stats['total_detections'] == 100
        assert stats['validated_detections'] == 70
        assert stats['degraded_detections'] == 30
        assert stats['validation_rate'] == 70.0
        assert stats['quality_level'] == 'FAIR'  # 70% is FAIR

        # Step 5: Filter detections by quality
        response = test_client.get(
            f"/api/detections/{session_id}?usable_only=true"
        )

        assert response.status_code == 200
        filtered_detections = response.json()

        # Should only return validated detections
        assert len(filtered_detections) == 70
        assert all(d['usable_for_validation'] is True for d in filtered_detections)

    def test_quality_warnings_appear_in_results_api(self, test_client, db_session):
        """Test that quality warnings are included in results API response"""
        # Create session with poor quality
        session_id = str(uuid4())
        test_session = TestSession(
            id=session_id,
            project_id=str(uuid4()),
            video_sequence_id=str(uuid4()),
            status="completed",
            timing_degraded=True
        )
        db_session.add(test_session)

        # Only degraded detections
        for i in range(10):
            detection = DetectionEvent(
                id=str(uuid4()),
                test_session_id=session_id,
                video_id=str(uuid4()),
                frame_number=i,
                timestamp=datetime.utcnow(),
                usable_for_validation=False,
                timing_degraded=True
            )
            db_session.add(detection)

        db_session.commit()

        # Get results
        response = test_client.get(f"/api/results/{session_id}")

        assert response.status_code == 200
        results = response.json()

        # Results should include quality warnings
        assert 'quality_warnings' in results
        assert len(results['quality_warnings']) > 0

        # Should have SOME_DEGRADED warning (since only 10 detections, but all degraded)
        assert any(w['severity'] in ['WARNING', 'ERROR'] for w in results['quality_warnings'])


class TestQualityAPIEndpoints:
    """Test quality-specific API endpoints"""

    def test_quality_metrics_endpoint(self, test_client, db_session):
        """Test /api/quality/metrics endpoint for global quality metrics"""
        # Create multiple sessions with varying quality
        sessions = []
        for i in range(5):
            session_id = str(uuid4())
            test_session = TestSession(
                id=session_id,
                project_id=str(uuid4()),
                video_sequence_id=str(uuid4()),
                status="completed"
            )
            db_session.add(test_session)

            # Varying quality: session 0=100%, 1=80%, 2=60%, 3=40%, 4=20%
            validated_count = 100 - (i * 20)
            for j in range(100):
                detection = DetectionEvent(
                    id=str(uuid4()),
                    test_session_id=session_id,
                    video_id=str(uuid4()),
                    frame_number=j,
                    timestamp=datetime.utcnow(),
                    usable_for_validation=(j < validated_count)
                )
                db_session.add(detection)

        db_session.commit()

        # Get global quality metrics
        response = test_client.get("/api/quality/metrics")

        assert response.status_code == 200
        metrics = response.json()

        # Verify global metrics
        assert 'total_sessions' in metrics
        assert 'average_validation_rate' in metrics
        assert 'total_detections' in metrics
        assert metrics['total_sessions'] == 5
        assert metrics['total_detections'] == 500  # 5 sessions * 100 detections

    def test_quality_dashboard_data(self, test_client, db_session):
        """Test quality dashboard data endpoint"""
        # Create test data
        session_id = str(uuid4())
        test_session = TestSession(
            id=session_id,
            project_id=str(uuid4()),
            video_sequence_id=str(uuid4()),
            status="completed"
        )
        db_session.add(test_session)

        # Mix of good and degraded
        for i in range(100):
            detection = DetectionEvent(
                id=str(uuid4()),
                test_session_id=session_id,
                video_id=str(uuid4()),
                frame_number=i,
                timestamp=datetime.utcnow(),
                usable_for_validation=(i % 2 == 0)  # 50% validated
            )
            db_session.add(detection)

        db_session.commit()

        # Get dashboard data
        response = test_client.get("/api/quality/dashboard")

        assert response.status_code == 200
        dashboard = response.json()

        # Verify dashboard structure
        assert 'recent_sessions' in dashboard
        assert 'quality_distribution' in dashboard
        assert 'trend_data' in dashboard


class TestQualityFiltering:
    """Test quality-based filtering in various endpoints"""

    def test_filter_detections_by_quality(self, test_client, db_session):
        """Test filtering detections by usable_for_validation flag"""
        session_id = str(uuid4())
        test_session = TestSession(
            id=session_id,
            project_id=str(uuid4()),
            video_sequence_id=str(uuid4()),
            status="completed"
        )
        db_session.add(test_session)

        # 60 validated, 40 degraded
        for i in range(100):
            detection = DetectionEvent(
                id=str(uuid4()),
                test_session_id=session_id,
                video_id=str(uuid4()),
                frame_number=i,
                timestamp=datetime.utcnow(),
                usable_for_validation=(i < 60)
            )
            db_session.add(detection)

        db_session.commit()

        # Test filter: usable_only=true
        response = test_client.get(
            f"/api/detections/{session_id}?usable_only=true"
        )
        assert response.status_code == 200
        assert len(response.json()) == 60

        # Test filter: degraded_only=true
        response = test_client.get(
            f"/api/detections/{session_id}?degraded_only=true"
        )
        assert response.status_code == 200
        assert len(response.json()) == 40

        # Test no filter: all detections
        response = test_client.get(f"/api/detections/{session_id}")
        assert response.status_code == 200
        assert len(response.json()) == 100


class TestQualityPerformance:
    """Test performance of quality tracking queries"""

    def test_quality_check_performance(self, test_client, db_session):
        """Test that quality checks are performant with large datasets"""
        import time

        session_id = str(uuid4())
        test_session = TestSession(
            id=session_id,
            project_id=str(uuid4()),
            video_sequence_id=str(uuid4()),
            status="completed"
        )
        db_session.add(test_session)

        # Create 10,000 detections
        for i in range(10000):
            detection = DetectionEvent(
                id=str(uuid4()),
                test_session_id=session_id,
                video_id=str(uuid4()),
                frame_number=i,
                timestamp=datetime.utcnow(),
                usable_for_validation=(i % 2 == 0)
            )
            db_session.add(detection)

            # Commit in batches
            if i % 1000 == 0:
                db_session.commit()

        db_session.commit()

        # Test quality check performance
        start_time = time.time()
        response = test_client.get(f"/api/quality/warnings/{session_id}")
        elapsed = time.time() - start_time

        assert response.status_code == 200
        # Quality check should complete in < 1 second even with 10k detections
        assert elapsed < 1.0, f"Quality check took {elapsed}s, expected < 1s"


class TestQualityEdgeCases:
    """Test edge cases in quality tracking"""

    def test_empty_session_quality_check(self, test_client, db_session):
        """Test quality check on session with no detections"""
        session_id = str(uuid4())
        test_session = TestSession(
            id=session_id,
            project_id=str(uuid4()),
            video_sequence_id=str(uuid4()),
            status="completed"
        )
        db_session.add(test_session)
        db_session.commit()

        response = test_client.get(f"/api/quality/warnings/{session_id}")

        assert response.status_code == 200
        warnings = response.json()

        # Should have NO_DETECTIONS warning
        assert any(w['code'] == 'NO_DETECTIONS' for w in warnings)

    def test_nonexistent_session_quality_check(self, test_client):
        """Test quality check on non-existent session"""
        fake_session_id = str(uuid4())

        response = test_client.get(f"/api/quality/warnings/{fake_session_id}")

        # Should return 404 or empty warnings
        assert response.status_code in [200, 404]

    def test_all_perfect_quality(self, test_client, db_session):
        """Test session with 100% validation rate"""
        session_id = str(uuid4())
        test_session = TestSession(
            id=session_id,
            project_id=str(uuid4()),
            video_sequence_id=str(uuid4()),
            status="completed"
        )
        db_session.add(test_session)

        # All 100 detections are validated
        for i in range(100):
            detection = DetectionEvent(
                id=str(uuid4()),
                test_session_id=session_id,
                video_id=str(uuid4()),
                frame_number=i,
                timestamp=datetime.utcnow(),
                usable_for_validation=True,
                timing_degraded=False
            )
            db_session.add(detection)

        db_session.commit()

        response = test_client.get(f"/api/quality/statistics/{session_id}")

        assert response.status_code == 200
        stats = response.json()

        assert stats['validation_rate'] == 100.0
        assert stats['quality_level'] == 'EXCELLENT'
        assert stats['degraded_detections'] == 0

        # Should have minimal or no warnings
        response = test_client.get(f"/api/quality/warnings/{session_id}")
        warnings = response.json()
        # Either no warnings, or only INFO level
        assert all(w['severity'] == 'INFO' for w in warnings) or len(warnings) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
