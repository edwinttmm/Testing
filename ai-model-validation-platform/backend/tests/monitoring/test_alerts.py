"""Tests for alerting system"""
import pytest
from datetime import datetime
from monitoring.alerts import Alert, AlertSeverity, AlertManager
from monitoring.metrics_collector import MetricsCollector


class TestAlert:
    """Test Alert dataclass"""

    def test_alert_creation(self):
        """Test creating an alert"""
        alert = Alert(
            AlertSeverity.WARNING,
            "Test alert message",
            {'key': 'value'}
        )

        assert alert.severity == AlertSeverity.WARNING
        assert alert.message == "Test alert message"
        assert alert.context == {'key': 'value'}
        assert isinstance(alert.timestamp, datetime)

    def test_alert_str(self):
        """Test alert string representation"""
        alert = Alert(AlertSeverity.ERROR, "Error occurred")
        assert str(alert) == "[ERROR] Error occurred"

    def test_alert_to_dict(self):
        """Test converting alert to dictionary"""
        alert = Alert(
            AlertSeverity.CRITICAL,
            "Critical issue",
            {'error_code': 500}
        )

        alert_dict = alert.to_dict()

        assert alert_dict['severity'] == 'critical'
        assert alert_dict['message'] == "Critical issue"
        assert alert_dict['context'] == {'error_code': 500}
        assert 'timestamp' in alert_dict


class TestAlertManager:
    """Test AlertManager class"""

    @pytest.fixture
    def manager(self):
        """Create fresh alert manager for each test"""
        manager = AlertManager()
        manager.alert_history.clear()
        manager.handlers.clear()
        return manager

    def test_register_handler(self, manager):
        """Test registering alert handler"""
        def test_handler(alert):
            pass

        manager.register_handler(test_handler)
        assert len(manager.handlers) == 1

    def test_send_alert(self, manager):
        """Test sending an alert"""
        received_alerts = []

        def test_handler(alert):
            received_alerts.append(alert)

        manager.register_handler(test_handler)
        manager.send_alert(AlertSeverity.INFO, "Test message", {'test': True})

        assert len(received_alerts) == 1
        assert len(manager.alert_history) == 1
        assert received_alerts[0].message == "Test message"

    def test_send_alert_multiple_handlers(self, manager):
        """Test sending alert to multiple handlers"""
        handler1_calls = []
        handler2_calls = []

        def handler1(alert):
            handler1_calls.append(alert)

        def handler2(alert):
            handler2_calls.append(alert)

        manager.register_handler(handler1)
        manager.register_handler(handler2)

        manager.send_alert(AlertSeverity.WARNING, "Test")

        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1

    def test_handler_exception_doesnt_break_others(self, manager):
        """Test that failing handler doesn't affect others"""
        successful_handler_calls = []

        def failing_handler(alert):
            raise Exception("Handler failed")

        def successful_handler(alert):
            successful_handler_calls.append(alert)

        manager.register_handler(failing_handler)
        manager.register_handler(successful_handler)

        manager.send_alert(AlertSeverity.ERROR, "Test")

        # Successful handler should still have been called
        assert len(successful_handler_calls) == 1

    def test_alert_history_limit(self, manager):
        """Test that alert history is limited"""
        manager.max_history = 10

        # Send more alerts than limit
        for i in range(15):
            manager.send_alert(AlertSeverity.INFO, f"Alert {i}")

        assert len(manager.alert_history) == 10
        # First alerts should have been removed
        assert manager.alert_history[0].message == "Alert 5"

    def test_check_timing_degradation_rate_critical(self, manager):
        """Test critical degradation rate alert"""
        collector = MetricsCollector()
        collector.reset_metrics()

        # Create scenario with 60% degradation (above 50% critical threshold)
        for i in range(10):
            degraded = i < 6
            collector.record_session_start(
                f"session_{i}",
                timing_degraded=degraded,
                timing_verified=not degraded
            )

        manager.check_timing_degradation_rate(collector)

        # Should have sent critical alert
        assert len(manager.alert_history) == 1
        assert manager.alert_history[0].severity == AlertSeverity.CRITICAL
        assert "degradation rate" in manager.alert_history[0].message.lower()

    def test_check_timing_degradation_rate_warning(self, manager):
        """Test warning degradation rate alert"""
        collector = MetricsCollector()
        collector.reset_metrics()

        # Create scenario with 30% degradation (above 25% warning threshold)
        for i in range(10):
            degraded = i < 3
            collector.record_session_start(
                f"session_{i}",
                timing_degraded=degraded,
                timing_verified=not degraded
            )

        manager.check_timing_degradation_rate(collector)

        assert len(manager.alert_history) == 1
        assert manager.alert_history[0].severity == AlertSeverity.WARNING

    def test_check_timing_degradation_rate_ok(self, manager):
        """Test no alert when degradation rate is acceptable"""
        collector = MetricsCollector()
        collector.reset_metrics()

        # Create scenario with 10% degradation (below thresholds)
        for i in range(10):
            degraded = i < 1
            collector.record_session_start(
                f"session_{i}",
                timing_degraded=degraded,
                timing_verified=not degraded
            )

        manager.check_timing_degradation_rate(collector)

        assert len(manager.alert_history) == 0

    def test_check_validation_rate_error(self, manager):
        """Test error alert for low validation rate"""
        collector = MetricsCollector()
        collector.reset_metrics()

        collector.record_session_start("session_1", timing_degraded=False, timing_verified=True)

        # Create 40% validation rate (below 50% error threshold)
        for i in range(40):
            collector.record_detection("session_1", usable_for_validation=True)
        for i in range(60):
            collector.record_detection("session_1", usable_for_validation=False)

        manager.check_validation_rate(collector)

        assert len(manager.alert_history) == 1
        assert manager.alert_history[0].severity == AlertSeverity.ERROR
        assert "validation rate" in manager.alert_history[0].message.lower()

    def test_check_validation_rate_warning(self, manager):
        """Test warning alert for reduced validation rate"""
        collector = MetricsCollector()
        collector.reset_metrics()

        collector.record_session_start("session_1", timing_degraded=False, timing_verified=True)

        # Create 60% validation rate (below 70% warning threshold)
        for i in range(60):
            collector.record_detection("session_1", usable_for_validation=True)
        for i in range(40):
            collector.record_detection("session_1", usable_for_validation=False)

        manager.check_validation_rate(collector)

        assert len(manager.alert_history) == 1
        assert manager.alert_history[0].severity == AlertSeverity.WARNING

    def test_check_all_thresholds(self, manager):
        """Test checking all thresholds at once"""
        collector = MetricsCollector()
        collector.reset_metrics()

        # Create scenario that triggers both alerts
        for i in range(10):
            collector.record_session_start(
                f"session_{i}",
                timing_degraded=i < 6,  # 60% degraded
                timing_verified=i >= 6
            )

        # Add detections with low validation rate
        for session_id in [f"session_{i}" for i in range(10)]:
            for j in range(4):  # 40% validation
                collector.record_detection(session_id, usable_for_validation=True)
            for j in range(6):
                collector.record_detection(session_id, usable_for_validation=False)

        manager.check_all_thresholds(collector)

        # Should have both alerts
        assert len(manager.alert_history) == 2

    def test_get_recent_alerts(self, manager):
        """Test getting recent alerts"""
        for i in range(10):
            severity = AlertSeverity.INFO if i % 2 == 0 else AlertSeverity.ERROR
            manager.send_alert(severity, f"Alert {i}")

        recent = manager.get_recent_alerts(limit=5)

        assert len(recent) == 5
        # Should be in reverse order (most recent first)
        assert recent[0]['message'] == "Alert 9"

    def test_get_recent_alerts_filtered(self, manager):
        """Test getting recent alerts filtered by severity"""
        manager.send_alert(AlertSeverity.INFO, "Info 1")
        manager.send_alert(AlertSeverity.ERROR, "Error 1")
        manager.send_alert(AlertSeverity.INFO, "Info 2")
        manager.send_alert(AlertSeverity.CRITICAL, "Critical 1")

        errors = manager.get_recent_alerts(severity=AlertSeverity.ERROR)

        assert len(errors) == 1
        assert errors[0]['message'] == "Error 1"

    def test_set_threshold(self, manager):
        """Test updating threshold"""
        original_value = manager.thresholds['degradation_rate_critical']

        manager.set_threshold('degradation_rate_critical', 60.0)

        assert manager.thresholds['degradation_rate_critical'] == 60.0
        assert manager.thresholds['degradation_rate_critical'] != original_value

    def test_get_thresholds(self, manager):
        """Test getting all thresholds"""
        thresholds = manager.get_thresholds()

        assert 'degradation_rate_critical' in thresholds
        assert 'degradation_rate_warning' in thresholds
        assert 'validation_rate_error' in thresholds
        assert 'validation_rate_warning' in thresholds

    def test_custom_threshold_affects_alerts(self, manager):
        """Test that custom thresholds affect alert behavior"""
        collector = MetricsCollector()
        collector.reset_metrics()

        # Set higher threshold
        manager.set_threshold('degradation_rate_critical', 80.0)

        # Create 60% degradation (below new threshold)
        for i in range(10):
            collector.record_session_start(
                f"session_{i}",
                timing_degraded=i < 6,
                timing_verified=i >= 6
            )

        manager.check_timing_degradation_rate(collector)

        # Should not send critical alert (60% < 80%)
        critical_alerts = [a for a in manager.alert_history if a.severity == AlertSeverity.CRITICAL]
        assert len(critical_alerts) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
