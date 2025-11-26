"""
Background Monitoring Service

Provides automatic background monitoring tasks including:
- Database connection pool health monitoring
- Periodic metrics collection
- Automatic threshold checking and alerting
- Resource usage tracking

Features:
- Runs in background thread
- Configurable check intervals
- Graceful shutdown support
- Error recovery and logging
- Zero-touch operation once configured

Usage:
    Add to main.py startup:

    from services.background_monitoring import start_background_monitoring

    @app.on_event("startup")
    async def setup_background_monitoring():
        start_background_monitoring()

Author: Backend Integration Agent
Date: 2025-11-19
"""

import time
import logging
import threading
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BackgroundMonitoringService:
    """Background monitoring service manager"""

    def __init__(
        self,
        pool_check_interval: int = 60,  # seconds
        metrics_check_interval: int = 300,  # seconds (5 minutes)
        threshold_check_interval: int = 600  # seconds (10 minutes)
    ):
        """
        Initialize background monitoring service

        Args:
            pool_check_interval: How often to check database pool (seconds)
            metrics_check_interval: How often to log metrics summary (seconds)
            threshold_check_interval: How often to check alert thresholds (seconds)
        """
        self.pool_check_interval = pool_check_interval
        self.metrics_check_interval = metrics_check_interval
        self.threshold_check_interval = threshold_check_interval

        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Lazy imports to avoid circular dependencies
        self._pool_monitor = None
        self._metrics_collector = None
        self._alert_manager = None

    @property
    def pool_monitor(self):
        """Lazy load pool monitor"""
        if self._pool_monitor is None:
            from utils.pool_monitor import PoolMonitor
            self._pool_monitor = PoolMonitor
        return self._pool_monitor

    @property
    def metrics_collector(self):
        """Lazy load metrics collector"""
        if self._metrics_collector is None:
            from monitoring.metrics_collector import metrics_collector
            self._metrics_collector = metrics_collector
        return self._metrics_collector

    @property
    def alert_manager(self):
        """Lazy load alert manager"""
        if self._alert_manager is None:
            from monitoring.alerts import alert_manager
            self._alert_manager = alert_manager
        return self._alert_manager

    def start(self):
        """Start background monitoring in a daemon thread"""
        if self._running:
            logger.warning("Background monitoring already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="BackgroundMonitoring"
        )
        self._thread.start()

        logger.info("✅ Background monitoring service started")
        logger.info(f"   Pool checks every {self.pool_check_interval}s")
        logger.info(f"   Metrics summary every {self.metrics_check_interval}s")
        logger.info(f"   Threshold checks every {self.threshold_check_interval}s")

    def stop(self):
        """Stop background monitoring gracefully"""
        if not self._running:
            return

        logger.info("Stopping background monitoring service...")
        self._running = False

        if self._thread and self._thread.is_alive():
            # Wait up to 5 seconds for thread to finish
            self._thread.join(timeout=5)

        logger.info("✅ Background monitoring service stopped")

    def _monitoring_loop(self):
        """Main monitoring loop (runs in background thread)"""
        logger.info("Background monitoring loop started")

        last_pool_check = 0
        last_metrics_check = 0
        last_threshold_check = 0

        while self._running:
            try:
                current_time = time.time()

                # 1. Pool Health Check
                if current_time - last_pool_check >= self.pool_check_interval:
                    self._check_pool_health()
                    last_pool_check = current_time

                # 2. Metrics Summary
                if current_time - last_metrics_check >= self.metrics_check_interval:
                    self._log_metrics_summary()
                    last_metrics_check = current_time

                # 3. Threshold Checks
                if current_time - last_threshold_check >= self.threshold_check_interval:
                    self._check_thresholds()
                    last_threshold_check = current_time

                # Sleep for 1 second before next iteration
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                time.sleep(5)  # Wait a bit longer after error

        logger.info("Background monitoring loop ended")

    def _check_pool_health(self):
        """Check database connection pool health"""
        try:
            status = self.pool_monitor.get_pool_status()

            # Log pool status
            logger.debug(
                f"📊 Pool Status: "
                f"{status['active_connections']}/{status['pool_size']} active, "
                f"{status['overflow_connections']} overflow"
            )

            # Check for issues
            pool_utilization = (
                status['active_connections'] / status['pool_size']
                if status['pool_size'] > 0 else 0
            )

            if pool_utilization > 0.9:
                logger.warning(
                    f"⚠️  High pool utilization: {pool_utilization*100:.0f}%"
                )

            if status.get('is_healthy') is False:
                logger.error("❌ Database pool is unhealthy!")

        except Exception as e:
            logger.error(f"Error checking pool health: {e}", exc_info=True)

    def _log_metrics_summary(self):
        """Log summary of current metrics"""
        try:
            summary = self.metrics_collector.get_global_summary()

            logger.info("=" * 60)
            logger.info("📊 METRICS SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total Sessions: {summary.get('total_sessions', 0)}")
            logger.info(f"Total Detections: {summary.get('total_detections', 0)}")

            degradation_rate = summary.get('degradation_rate', 0)
            if degradation_rate > 0:
                logger.info(f"Degradation Rate: {degradation_rate:.1f}%")

            validation_rate = summary.get('validation_rate', 100)
            logger.info(f"Validation Rate: {validation_rate:.1f}%")

            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error logging metrics summary: {e}", exc_info=True)

    def _check_thresholds(self):
        """Check alert thresholds and send alerts if needed"""
        try:
            # Trigger automatic threshold checks
            self.alert_manager.check_all_thresholds(self.metrics_collector)

            logger.debug("✅ Threshold checks completed")

        except Exception as e:
            logger.error(f"Error checking thresholds: {e}", exc_info=True)


# Global instance
_monitoring_service: Optional[BackgroundMonitoringService] = None


def start_background_monitoring(
    pool_check_interval: int = 60,
    metrics_check_interval: int = 300,
    threshold_check_interval: int = 600
):
    """
    Start background monitoring service (singleton)

    Args:
        pool_check_interval: Pool check interval in seconds
        metrics_check_interval: Metrics logging interval in seconds
        threshold_check_interval: Threshold checking interval in seconds
    """
    global _monitoring_service

    if _monitoring_service is None:
        _monitoring_service = BackgroundMonitoringService(
            pool_check_interval=pool_check_interval,
            metrics_check_interval=metrics_check_interval,
            threshold_check_interval=threshold_check_interval
        )

    _monitoring_service.start()


def stop_background_monitoring():
    """Stop background monitoring service"""
    global _monitoring_service

    if _monitoring_service is not None:
        _monitoring_service.stop()


def get_monitoring_service() -> Optional[BackgroundMonitoringService]:
    """Get current monitoring service instance"""
    return _monitoring_service
