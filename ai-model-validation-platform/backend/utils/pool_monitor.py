"""Connection pool monitoring and leak detection

This module provides real-time monitoring of the database connection pool
to detect and prevent connection leaks and pool exhaustion.

Key Features:
- Real-time pool statistics
- Connection leak detection
- High utilization warnings
- Performance metrics
"""

from database import engine
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PoolMonitor:
    """Monitor database connection pool health and detect leaks"""

    # Track high utilization periods
    _high_utilization_start: Optional[datetime] = None
    _leak_warnings: int = 0

    @staticmethod
    def get_pool_status() -> Dict[str, any]:
        """
        Get current pool statistics.

        Returns:
            Dictionary with pool metrics:
            - size: Total pool size
            - checked_in: Available connections
            - checked_out: Active connections
            - overflow: Overflow connections created
            - max_overflow: Maximum overflow allowed
            - utilization: Percentage of pool in use
        """
        try:
            pool = engine.pool

            size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()
            max_overflow = pool._max_overflow

            # Calculate utilization percentage
            total_capacity = size + max_overflow
            utilization = (checked_out / total_capacity * 100) if total_capacity > 0 else 0

            return {
                'size': size,
                'checked_in': checked_in,
                'checked_out': checked_out,
                'overflow': overflow,
                'max_overflow': max_overflow,
                'utilization': round(utilization, 1),
                'total_capacity': total_capacity,
                'available': checked_in + (max_overflow - overflow)
            }
        except Exception as e:
            logger.error(f"Failed to get pool status: {e}")
            return {
                'error': str(e),
                'status': 'unknown'
            }

    @staticmethod
    def log_pool_status():
        """Log current pool status with appropriate severity"""
        status = PoolMonitor.get_pool_status()

        if 'error' in status:
            logger.error(f"❌ Connection Pool Error: {status['error']}")
            return

        utilization = status['utilization']

        # Build status message
        msg = (
            f"📊 Connection Pool: "
            f"{status['checked_out']}/{status['size']} in use, "
            f"{status['overflow']} overflow, "
            f"{status['utilization']}% utilization "
            f"({status['available']} available)"
        )

        # Log with appropriate severity
        if utilization >= 90:
            logger.error(f"🚨 CRITICAL: {msg}")
        elif utilization >= 80:
            logger.warning(f"⚠️ HIGH: {msg}")
        elif utilization >= 60:
            logger.info(msg)
        else:
            logger.debug(msg)

        # Track high utilization periods
        if utilization >= 80:
            if PoolMonitor._high_utilization_start is None:
                PoolMonitor._high_utilization_start = datetime.now()
            else:
                duration = datetime.now() - PoolMonitor._high_utilization_start
                if duration > timedelta(minutes=5):
                    logger.error(
                        f"🚨 Connection pool at {utilization}% for {duration.seconds}s - "
                        "possible leak or undersized pool"
                    )
        else:
            PoolMonitor._high_utilization_start = None

    @staticmethod
    def check_for_leaks() -> bool:
        """
        Check for potential connection leaks.

        Returns:
            True if leak detected, False otherwise

        Leak Detection Rules:
            1. All connections checked out for extended period
            2. High utilization (>90%) sustained for >2 minutes
            3. Overflow connections constantly created
        """
        status = PoolMonitor.get_pool_status()

        if 'error' in status:
            return False

        leak_detected = False

        # Rule 1: All connections checked out
        if status['checked_out'] >= status['size'] and status['overflow'] >= status['max_overflow']:
            PoolMonitor._leak_warnings += 1
            logger.error(
                f"🚨 Possible connection leak: All {status['total_capacity']} "
                f"connections checked out (warning #{PoolMonitor._leak_warnings})"
            )
            leak_detected = True

        # Rule 2: Sustained high utilization
        if status['utilization'] >= 90:
            if PoolMonitor._high_utilization_start:
                duration = datetime.now() - PoolMonitor._high_utilization_start
                if duration > timedelta(minutes=2):
                    logger.error(
                        f"🚨 Connection leak suspected: {status['utilization']}% "
                        f"utilization for {duration.seconds}s"
                    )
                    leak_detected = True

        # Rule 3: Constant overflow
        if status['overflow'] >= status['max_overflow']:
            logger.warning(
                f"⚠️ Pool exhaustion: Using maximum overflow "
                f"({status['overflow']}/{status['max_overflow']})"
            )

        # Reset warnings if pool recovers
        if status['utilization'] < 50:
            PoolMonitor._leak_warnings = 0

        return leak_detected

    @staticmethod
    def get_recommendations() -> list:
        """
        Get recommendations based on current pool status.

        Returns:
            List of recommendation strings
        """
        status = PoolMonitor.get_pool_status()

        if 'error' in status:
            return ["Unable to analyze pool - check database connection"]

        recommendations = []
        utilization = status['utilization']

        # High utilization recommendations
        if utilization >= 90:
            recommendations.append(
                "🚨 CRITICAL: Increase pool_size and max_overflow in database.py"
            )
            recommendations.append(
                "Check for connection leaks - ensure all SessionLocal() calls have .close()"
            )
        elif utilization >= 80:
            recommendations.append(
                "⚠️ WARNING: Pool utilization high - monitor for leaks"
            )

        # Overflow usage recommendations
        if status['overflow'] > 0:
            recommendations.append(
                f"Using {status['overflow']} overflow connections - "
                "consider increasing pool_size"
            )

        # Leak detection recommendations
        if PoolMonitor.check_for_leaks():
            recommendations.append(
                "🔍 Scan codebase for 'SessionLocal()' without 'finally: db.close()'"
            )
            recommendations.append(
                "Use 'managed_db_session()' context manager to prevent leaks"
            )

        # All good
        if not recommendations:
            recommendations.append(
                "✅ Connection pool healthy - no action needed"
            )

        return recommendations

    @staticmethod
    def detailed_report() -> str:
        """
        Generate detailed pool health report.

        Returns:
            Formatted multi-line report string
        """
        status = PoolMonitor.get_pool_status()
        recommendations = PoolMonitor.get_recommendations()

        report = [
            "=" * 60,
            "DATABASE CONNECTION POOL HEALTH REPORT",
            "=" * 60,
            "",
            "Current Status:",
            f"  Pool Size: {status.get('size', 'N/A')}",
            f"  Checked Out: {status.get('checked_out', 'N/A')}",
            f"  Checked In: {status.get('checked_in', 'N/A')}",
            f"  Overflow: {status.get('overflow', 'N/A')}/{status.get('max_overflow', 'N/A')}",
            f"  Utilization: {status.get('utilization', 'N/A')}%",
            f"  Available: {status.get('available', 'N/A')}",
            "",
            "Recommendations:",
        ]

        for rec in recommendations:
            report.append(f"  - {rec}")

        report.extend([
            "",
            "=" * 60
        ])

        return "\n".join(report)


def monitor_pool_health():
    """Convenience function to log pool health"""
    PoolMonitor.log_pool_status()
    PoolMonitor.check_for_leaks()


def get_pool_report():
    """Convenience function to get detailed report"""
    return PoolMonitor.detailed_report()
