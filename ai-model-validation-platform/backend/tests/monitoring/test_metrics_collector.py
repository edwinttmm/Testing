"""Tests for metrics collection system"""
import pytest
from datetime import datetime
import threading
import time
from monitoring.metrics_collector import MetricsCollector, SessionMetrics


class TestSessionMetrics:
    """Test SessionMetrics dataclass"""

    def test_validation_rate_with_detections(self):
        """Test validation rate calculation with detections"""
        metrics = SessionMetrics(
            session_id="test_session",
            start_time=datetime.now(),
            timing_degraded=False,
            timing_verified=True,
            total_detections=100,
            validated_detections=90,
            degraded_detections=10
        )

        assert metrics.validation_rate == 90.0

    def test_validation_rate_zero_detections(self):
        """Test validation rate with zero detections"""
        metrics = SessionMetrics(
            session_id="test_session",
            start_time=datetime.now(),
            timing_degraded=False,
            timing_verified=True,
            total_detections=0,
            validated_detections=0,
            degraded_detections=0
        )

        assert metrics.validation_rate == 0.0

    def test_degradation_rate(self):
        """Test degradation rate calculation"""
        metrics = SessionMetrics(
            session_id="test_session",
            start_time=datetime.now(),
            timing_degraded=True,
            timing_verified=False,
            total_detections=50,
            validated_detections=40,
            degraded_detections=10
        )

        assert metrics.degradation_rate == 20.0


class TestMetricsCollector:
    """Test MetricsCollector class"""

    @pytest.fixture
    def collector(self):
        """Create fresh collector for each test"""
        collector = MetricsCollector()
        collector.reset_metrics()
        return collector

    def test_record_session_start(self, collector):
        """Test recording session start"""
        collector.record_session_start(
            session_id="session_1",
            timing_degraded=False,
            timing_verified=True
        )

        assert collector.global_stats['total_sessions'] == 1
        assert collector.global_stats['verified_sessions'] == 1
        assert collector.global_stats['degraded_sessions'] == 0
        assert "session_1" in collector.session_metrics

    def test_record_session_start_degraded(self, collector):
        """Test recording session with degraded timing"""
        collector.record_session_start(
            session_id="session_1",
            timing_degraded=True,
            timing_verified=False
        )

        assert collector.global_stats['total_sessions'] == 1
        assert collector.global_stats['verified_sessions'] == 0
        assert collector.global_stats['degraded_sessions'] == 1

    def test_record_detection(self, collector):
        """Test recording detection event"""
        # First create session
        collector.record_session_start(
            session_id="session_1",
            timing_degraded=False,
            timing_verified=True
        )

        # Record detections
        collector.record_detection("session_1", usable_for_validation=True)
        collector.record_detection("session_1", usable_for_validation=True)
        collector.record_detection("session_1", usable_for_validation=False)

        metrics = collector.get_session_summary("session_1")
        assert metrics['total_detections'] == 3
        assert metrics['validated_detections'] == 2
        assert metrics['degraded_detections'] == 1
        assert metrics['validation_rate'] == pytest.approx(66.67, rel=0.01)

    def test_record_detection_auto_creates_session(self, collector):
        """Test that recording detection auto-creates session if not exists"""
        collector.record_detection("new_session", usable_for_validation=True)

        assert "new_session" in collector.session_metrics
        assert collector.global_stats['total_sessions'] == 1

    def test_get_session_summary(self, collector):
        """Test getting session summary"""
        collector.record_session_start(
            session_id="session_1",
            timing_degraded=False,
            timing_verified=True
        )
        collector.record_detection("session_1", usable_for_validation=True)

        summary = collector.get_session_summary("session_1")

        assert summary is not None
        assert summary['session_id'] == "session_1"
        assert summary['timing_degraded'] is False
        assert summary['timing_verified'] is True
        assert 'start_time' in summary
        assert summary['total_detections'] == 1

    def test_get_session_summary_not_found(self, collector):
        """Test getting summary for non-existent session"""
        summary = collector.get_session_summary("nonexistent")
        assert summary is None

    def test_get_global_summary(self, collector):
        """Test getting global summary"""
        # Create multiple sessions
        collector.record_session_start("session_1", timing_degraded=False, timing_verified=True)
        collector.record_session_start("session_2", timing_degraded=True, timing_verified=False)
        collector.record_session_start("session_3", timing_degraded=False, timing_verified=True)

        # Add detections
        for i in range(5):
            collector.record_detection("session_1", usable_for_validation=True)
        for i in range(3):
            collector.record_detection("session_2", usable_for_validation=False)

        summary = collector.get_global_summary()

        assert summary['total_sessions'] == 3
        assert summary['degraded_sessions'] == 1
        assert summary['verified_sessions'] == 2
        assert summary['total_detections'] == 8
        assert summary['validated_detections'] == 5
        assert summary['degraded_detections'] == 3
        assert summary['degradation_rate'] == pytest.approx(33.33, rel=0.01)
        assert summary['validation_rate'] == pytest.approx(62.5, rel=0.01)

    def test_get_recent_sessions(self, collector):
        """Test getting recent sessions"""
        # Create 5 sessions
        for i in range(5):
            collector.record_session_start(f"session_{i}", timing_degraded=False, timing_verified=True)

        recent = collector.get_recent_sessions(limit=3)

        assert len(recent) == 3
        # Should be in reverse order (most recent first)
        assert recent[0]['session_id'] == "session_4"
        assert recent[1]['session_id'] == "session_3"
        assert recent[2]['session_id'] == "session_2"

    def test_thread_safety(self, collector):
        """Test thread-safe operations"""
        def add_sessions(thread_id):
            for i in range(10):
                session_id = f"thread_{thread_id}_session_{i}"
                collector.record_session_start(session_id, timing_degraded=False, timing_verified=True)
                collector.record_detection(session_id, usable_for_validation=True)
                time.sleep(0.001)  # Small delay to encourage race conditions

        threads = []
        for i in range(5):
            thread = threading.Thread(target=add_sessions, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        summary = collector.get_global_summary()
        assert summary['total_sessions'] == 50
        assert summary['total_detections'] == 50

    def test_reset_metrics(self, collector):
        """Test resetting metrics"""
        # Add some data
        collector.record_session_start("session_1", timing_degraded=False, timing_verified=True)
        collector.record_detection("session_1", usable_for_validation=True)

        # Reset
        collector.reset_metrics()

        # Verify everything is cleared
        summary = collector.get_global_summary()
        assert summary['total_sessions'] == 0
        assert summary['total_detections'] == 0
        assert len(collector.session_metrics) == 0
        assert len(collector.session_history) == 0

    def test_high_degradation_scenario(self, collector):
        """Test scenario with high timing degradation"""
        # Create 10 sessions, 8 degraded
        for i in range(10):
            degraded = i < 8
            collector.record_session_start(
                f"session_{i}",
                timing_degraded=degraded,
                timing_verified=not degraded
            )

        summary = collector.get_global_summary()
        assert summary['degradation_rate'] == 80.0

    def test_low_validation_scenario(self, collector):
        """Test scenario with low validation rate"""
        collector.record_session_start("session_1", timing_degraded=False, timing_verified=True)

        # Add 100 detections, only 30 validated
        for i in range(30):
            collector.record_detection("session_1", usable_for_validation=True)
        for i in range(70):
            collector.record_detection("session_1", usable_for_validation=False)

        summary = collector.get_global_summary()
        assert summary['validation_rate'] == 30.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
