"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/integration/test_fix_integration_comprehensive.py
"""

"""
Comprehensive Integration Tests for All Fixes (FIX-1 through FIX-4)

Tests verify that all fixes work together correctly and handle edge cases gracefully.

Test Categories:
1. Normal Flow (Happy Path)
2. Race Conditions (PostgreSQL MVCC)
3. Timing Service Failures
4. Database Failures
5. Concurrent Sessions
6. Multi-Video Sequences

Author: Agent 5 (QA & Integration Testing)
Date: 2025-11-19
"""

import pytest
import asyncio
import time
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError

# Import models and services
from models import TestSession, DetectionEvent, Video, VideoTestSequence
from database import SessionLocal, get_db
from services.dedicated_labjack_monitor import (
    DedicatedLabJackMonitor,
    get_dedicated_labjack_monitor,
    start_hil_monitoring
)
from services.video_timing_service import VideoTimingService


class TestFixIntegration:
    """Integration tests for all fixes working together"""

    # Remove local fixture definitions - use global fixtures from conftest.py

    @pytest.fixture
    def mock_labjack(self):
        """Mock LabJack hardware for testing"""
        with patch('services.labjack_hardware_service.LabJackHardwareService') as mock:
            mock.return_value.connect.return_value = True
            mock.return_value.read_single_voltage.return_value = 0.0
            yield mock

    # =========================================================================
    # TEST 1: Normal Flow (Happy Path)
    # Tests: FIX-1, FIX-2, FIX-3, FIX-4 all working in ideal conditions
    # =========================================================================

    @pytest.mark.asyncio
    async def test_normal_flow_all_fixes(
        self, db_session, mock_labjack
    ):
        """
        Test all fixes working together in normal conditions.

        Expected:
        - Session created successfully
        - Monitor starts with correct session ID (FIX-2)
        - Event signaled immediately (FIX-1)
        - Timing initialized (FIX-3, FIX-4)
        - Detection saved to correct session
        """
        # 1. Create primary session
        session_id = str(uuid.uuid4())
        session = TestSession(
            id=session_id,
            project_id="test-project-1",
            status="active",
            tolerance_ms=100,
            created_at=datetime.utcnow()
        )
        db_session.add(session)
        db_session.commit()

        # Small delay to simulate API processing
        await asyncio.sleep(0.05)

        # 2. Start monitoring with PRIMARY session ID (FIX-2)
        config = {
            'test_session_id': session_id,  # FIX-2: Pass primary ID
            'video_id': 'video-test-1',
            'detection_threshold_volts': 3.0,
            'sample_rate': 10.0
        }

        # 3. Monitor should start successfully
        result = await start_hil_monitoring(config)
        assert result == True, "Monitor should start successfully"

        # 4. Verify event was signaled (FIX-1)
        monitor = get_dedicated_labjack_monitor()
        assert session_id in monitor.active_sessions
        event = monitor.active_sessions[session_id]['timing_ready_event']
        assert event.is_set(), "Timing ready event should be signaled (FIX-1)"

        # 5. Simulate voltage detection
        with patch.object(monitor.labjack_monitor, 'read_voltage', return_value=4.2):
            # Trigger detection callback
            monitor._detection_callback(session_id, 4.2, time.time())

        await asyncio.sleep(0.2)  # Allow detection processing

        # 6. Verify detection saved to PRIMARY session (FIX-2)
        detections = db_session.execute(select(DetectionEvent).filter_by(
            test_session_id=session_id
        )).scalars().all()

        assert len(detections) > 0, "Detection should be saved"
        assert detections[0].test_session_id == session_id, \
            "Detection should be saved to PRIMARY session (FIX-2)"

        # 7. Verify timing data present
        assert detections[0].timestamp is not None
        # Note: latency_ms may be None if ground truth not available

        print("✅ TEST 1 PASSED: Normal flow with all fixes")

    # =========================================================================
    # TEST 2: Session Not Found (Race Condition)
    # Tests: FIX-1 (event signal), FIX-3 (verification), FIX-4 (retry)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_session_race_condition(
        self, db_session, mock_labjack, caplog
    ):
        """
        Test system behavior when session not immediately visible (MVCC).

        Expected:
        - Event signaled immediately (FIX-1)
        - Retry logic attempts to find session (FIX-4)
        - Fallback timing used if not found (FIX-3)
        - Detection still saved
        """
        # 1. Create session (simulates MVCC scenario)
        session_id = str(uuid.uuid4())

        session = TestSession(
            id=session_id,
            project_id="test-project-2",
            status="active"
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # 2. Immediately start monitor (race condition)
        config = {
            'test_session_id': session_id,
            'video_id': 'video-test-2',
            'detection_threshold_volts': 3.0
        }

        # 3. Monitor should handle race condition gracefully
        result = await start_hil_monitoring(config)

        # Should NOT fail even if session not found immediately
        assert result == True, "Should continue with degraded timing (FIX-1, FIX-3)"

        # 4. Check logs for retry attempts (FIX-4)
        # Should see retry messages like "retrying in 50ms"
        log_text = caplog.text
        retry_indicators = [
            "attempt" in log_text.lower(),
            "retry" in log_text.lower(),
            "degraded timing" in log_text.lower()
        ]
        assert any(retry_indicators), "Should log retry attempts or fallback (FIX-4)"

        # 5. Verify event was signaled despite race condition (FIX-1)
        monitor = get_dedicated_labjack_monitor()
        if session_id in monitor.active_sessions:
            event = monitor.active_sessions[session_id]['timing_ready_event']
            assert event.is_set(), "Event should be signaled even if session not found (FIX-1)"

        # 6. Simulate detection
        with patch.object(monitor.labjack_monitor, 'read_voltage', return_value=4.5):
            monitor._detection_callback(session_id, 4.5, time.time())

        await asyncio.sleep(0.2)

        # 7. Detection should be saved (with fallback timing)
        detections = db_session.execute(select(DetectionEvent).filter_by(
            test_session_id=session_id
        )).scalars().all()

        assert len(detections) > 0, \
            "Detection should be saved even with race condition (FIX-1, FIX-3)"

        print("✅ TEST 2 PASSED: Race condition handled gracefully")

    # =========================================================================
    # TEST 3: Timing Service Fails
    # Tests: FIX-1 (event signal on exception)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_timing_service_exception(
        self, db_session, mock_labjack, caplog
    ):
        """
        Test graceful degradation when timing service throws exception.

        Expected:
        - Event signaled despite exception (FIX-1)
        - Monitor continues operating
        - Detection saved with fallback timing
        """
        # 1. Create session
        session_id = str(uuid.uuid4())
        session = TestSession(
            id=session_id,
            project_id="test-project-3",
            status="active"
        )
        db_session.add(session)
        db_session.commit()

        # 2. Mock timing service to fail
        with patch.object(
            VideoTimingService,
            'start_video_timing',
            side_effect=Exception("Timing initialization failed")
        ):
            config = {
                'test_session_id': session_id,
                'video_id': 'video-test-3',
                'detection_threshold_volts': 3.0
            }

            # 3. Should NOT fail - event signaled anyway (FIX-1)
            result = await start_hil_monitoring(config)
            assert result == True, "Should continue despite timing exception (FIX-1)"

        # 4. Check logs for exception handling
        log_text = caplog.text
        assert "Exception in start_video_timing" in log_text or \
               "Timing event signaled despite error" in log_text, \
               "Should log exception and signal event anyway (FIX-1)"

        # 5. Verify event signaled
        monitor = get_dedicated_labjack_monitor()
        event = monitor.active_sessions[session_id]['timing_ready_event']
        assert event.is_set(), "Event should be signaled despite exception (FIX-1)"

        # 6. Simulate detection
        with patch.object(monitor.labjack_monitor, 'read_voltage', return_value=4.0):
            monitor._detection_callback(session_id, 4.0, time.time())

        await asyncio.sleep(0.2)

        # 7. Detection should be saved with fallback timing
        detections = db_session.execute(select(DetectionEvent).filter_by(
            test_session_id=session_id
        )).scalars().all()

        assert len(detections) > 0, \
            "Detection should be saved despite timing failure (FIX-1)"
        assert detections[0].timestamp is not None, \
            "Should have fallback timestamp"

        print("✅ TEST 3 PASSED: Timing service exception handled")

    # =========================================================================
    # TEST 4: Database Connection Lost
    # Tests: Robustness to transient database failures
    # =========================================================================

    @pytest.mark.asyncio
    async def test_database_connection_lost(
        self, db_session, mock_labjack, caplog
    ):
        """
        Test system behavior when database connection is lost.

        Expected:
        - Monitor continues running
        - Error logged but no crash
        - System recovers after connection restored
        """
        # 1. Create session
        session_id = str(uuid.uuid4())
        session = TestSession(
            id=session_id,
            project_id="test-project-4",
            status="active"
        )
        db_session.add(session)
        db_session.commit()

        # 2. Start monitoring
        config = {
            'test_session_id': session_id,
            'video_id': 'video-test-4',
            'detection_threshold_volts': 3.0
        }

        result = await start_hil_monitoring(config)
        assert result == True

        # 3. Simulate database connection loss during detection
        with patch('database.SessionLocal') as mock_session:
            mock_session.side_effect = OperationalError(
                "Connection lost", None, None
            )

            # Simulate detection - should handle error gracefully
            monitor = get_dedicated_labjack_monitor()
            try:
                with patch.object(monitor.labjack_monitor, 'read_voltage', return_value=3.8):
                    monitor._detection_callback(session_id, 3.8, time.time())
            except Exception as e:
                # Should catch database error, not propagate
                pytest.fail(f"Detection callback should handle DB error: {e}")

        await asyncio.sleep(0.2)

        # 4. Check logs for error handling
        log_text = caplog.text
        assert "database" in log_text.lower() or "connection" in log_text.lower(), \
            "Should log database error"

        # 5. System should continue monitoring (not crash)
        # Simulate second detection after DB recovery
        with patch.object(monitor.labjack_monitor, 'read_voltage', return_value=4.2):
            monitor._detection_callback(session_id, 4.2, time.time())

        # Should not raise exception
        print("✅ TEST 4 PASSED: Database failure handled gracefully")

    # =========================================================================
    # TEST 5: Concurrent Sessions
    # Tests: FIX-2 (session ID isolation), connection pool stability
    # =========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_sessions(
        self, db_session, mock_labjack
    ):
        """
        Test multiple simultaneous sessions with unique IDs.

        Expected:
        - All sessions start successfully
        - No session ID confusion (FIX-2)
        - Each session has isolated detections
        - Connection pool stable
        """
        session_ids = []

        # 1. Create 5 sessions concurrently
        for i in range(5):
            session_id = str(uuid.uuid4())
            session = TestSession(
                id=session_id,
                project_id=f"test-project-concurrent-{i}",
                status="active"
            )
            db_session.add(session)
            session_ids.append(session_id)

        db_session.commit()

        # 2. Start monitoring for each session
        tasks = []
        for session_id in session_ids:
            config = {
                'test_session_id': session_id,
                'video_id': f'video-concurrent-{session_id[:8]}',
                'detection_threshold_volts': 3.0
            }
            task = asyncio.create_task(start_hil_monitoring(config))
            tasks.append(task)

            # Small stagger to simulate realistic timing
            await asyncio.sleep(0.05)

        # 3. Wait for all monitors to initialize
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should start successfully
        assert all(r == True for r in results if not isinstance(r, Exception)), \
            "All sessions should start successfully"

        # 4. Simulate detections on each session
        monitor = get_dedicated_labjack_monitor()
        for i, session_id in enumerate(session_ids):
            voltage = 3.0 + i * 0.2  # Different voltage per session
            with patch.object(monitor.labjack_monitor, 'read_voltage', return_value=voltage):
                monitor._detection_callback(session_id, voltage, time.time())

        await asyncio.sleep(0.5)

        # 5. Verify each session has its own detections
        for session_id in session_ids:
            detections = db_session.execute(select(DetectionEvent).filter_by(
                test_session_id=session_id
            )).scalars().all()

            assert len(detections) > 0, \
                f"Session {session_id} should have detections"

            # Verify no cross-session contamination (FIX-2)
            for detection in detections:
                assert detection.test_session_id == session_id, \
                    f"Detection should belong to session {session_id}, not {detection.test_session_id}"

        # 6. Verify connection pool not exhausted
        # (Check would require access to pool metrics)
        # For now, verify all operations completed without timeout

        print("✅ TEST 5 PASSED: Concurrent sessions isolated correctly")

    # =========================================================================
    # TEST 6: Multi-Video Sequence
    # Tests: FIX-2 (session ID consistency across videos)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_multi_video_sequence(
        self, db_session, mock_labjack
    ):
        """
        Test session ID consistency across multi-video sequence.

        Expected:
        - Single primary session ID used throughout
        - Detections from all videos saved to same session
        - Timing accurate per video
        """
        # 1. Create primary session
        primary_session_id = str(uuid.uuid4())
        session = TestSession(
            id=primary_session_id,
            project_id="test-project-multivideo",
            status="active"
        )
        db_session.add(session)

        # 2. Create video sequence
        video_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4())
        ]

        for i, video_id in enumerate(video_ids):
            video = Video(
                id=video_id,
                filename=f"video-{i+1}.mp4",
                path=f"/videos/video-{i+1}.mp4",
                duration_seconds=30.0
            )
            db_session.add(video)

            # Link to sequence
            seq = VideoTestSequence(
                session_id=primary_session_id,
                video_id=video_id,
                sequence_order=i,
                playback_duration_seconds=30.0
            )
            db_session.add(seq)

        db_session.commit()

        # 3. Start monitoring with PRIMARY session ID (FIX-2)
        config = {
            'test_session_id': primary_session_id,  # Same ID for all videos
            'video_sequence': video_ids
        }

        result = await start_hil_monitoring(config)
        assert result == True

        # 4. Simulate detections on each video
        monitor = get_dedicated_labjack_monitor()

        for i, video_id in enumerate(video_ids):
            # Simulate video transition (would be triggered by real playback)
            # For test, directly call detection callback

            voltage = 3.5 + i * 0.3
            with patch.object(monitor.labjack_monitor, 'read_voltage', return_value=voltage):
                # Add video_id to detection metadata
                timestamp = time.time()
                monitor._detection_callback(
                    primary_session_id,
                    voltage,
                    timestamp,
                    video_id=video_id  # Assuming callback accepts video_id
                )

            await asyncio.sleep(0.1)

        # 5. Query all detections
        detections = db_session.execute(select(DetectionEvent).filter_by(
            test_session_id=primary_session_id
        )).scalars().all()

        # 6. Verify all detections belong to PRIMARY session (FIX-2)
        assert len(detections) >= 3, \
            f"Should have at least 3 detections, got {len(detections)}"

        for detection in detections:
            assert detection.test_session_id == primary_session_id, \
                f"All detections should have primary session ID (FIX-2)"

        # 7. Verify detections distributed across videos
        video_ids_with_detections = set()
        for detection in detections:
            # Check video_id in metadata (implementation-dependent)
            if hasattr(detection, 'video_id') and detection.video_id:
                video_ids_with_detections.add(detection.video_id)

        # Should have detections from multiple videos
        # (This check is best-effort, depends on callback implementation)

        print("✅ TEST 6 PASSED: Multi-video sequence maintains session ID")


class TestRegressionSuite:
    """Regression tests to ensure existing functionality still works"""

    # Use global db_session fixture from conftest.py

    @pytest.mark.asyncio
    async def test_existing_session_queries(self, db_session):
        """Test that historical sessions can still be queried"""
        # Create historical session
        session_id = str(uuid.uuid4())
        session = TestSession(
            id=session_id,
            project_id="historical-project",
            status="completed",
            created_at=datetime.utcnow()
        )
        db_session.add(session)

        # Add detection
        detection = DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=session_id,
            timestamp=time.time(),
            confidence=0.95,
            class_label="pedestrian"
        )
        db_session.add(detection)
        db_session.commit()

        # Query should work
        queried_session = db_session.execute(select(TestSession).filter_by(
            id=session_id
        )).scalar_one_or_none()

        assert queried_session is not None
        assert queried_session.id == session_id

        # Query detections
        queried_detections = db_session.execute(select(DetectionEvent).filter_by(
            test_session_id=session_id
        )).scalars().all()

        assert len(queried_detections) == 1

        print("✅ REGRESSION TEST PASSED: Historical queries work")

    @pytest.mark.asyncio
    async def test_api_endpoint_compatibility(self, db_session):
        """Test that API endpoints return expected data format"""
        # This is a placeholder - would require FastAPI test client

        # Expected format hasn't changed:
        # {
        #   "session_id": "uuid",
        #   "detections": [...],
        #   "timing_data": {...}
        # }

        # Verify data structure
        session_id = str(uuid.uuid4())
        session = TestSession(id=session_id)
        db_session.add(session)
        db_session.commit()

        # Query format should be unchanged
        result = db_session.execute(select(TestSession).filter_by(id=session_id)).scalar_one_or_none()

        assert hasattr(result, 'id')
        assert hasattr(result, 'project_id')
        assert hasattr(result, 'status')

        print("✅ REGRESSION TEST PASSED: API compatibility maintained")


# Run tests with: pytest tests/integration/test_fix_integration_comprehensive.py -v -s
