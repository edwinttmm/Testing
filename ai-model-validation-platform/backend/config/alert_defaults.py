"""
Alert System Default Configuration

Provides intelligent default configuration for the alert system
based on environment variables and best practices.

Features:
- Environment-based configuration
- Sensible defaults for production use
- Multiple handler types (console, file, email, webhook, Slack)
- Easy customization via environment variables
- Automatic handler registration

Usage:
    from config.alert_defaults import configure_default_alerts

    # In main.py startup:
    configure_default_alerts()

Author: Backend Integration Agent
Date: 2025-11-19
"""

import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean from environment variable"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')


def get_env_int(key: str, default: int) -> int:
    """Get integer from environment variable"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def get_env_float(key: str, default: float) -> float:
    """Get float from environment variable"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def get_alert_thresholds() -> Dict[str, float]:
    """
    Get alert thresholds from environment or use intelligent defaults

    Environment Variables:
        ALERT_DEGRADATION_THRESHOLD: % of degraded detections (default: 25%)
        ALERT_VALIDATION_THRESHOLD: % of usable detections (default: 75%)
        ALERT_TIMING_THRESHOLD: % of sessions with timing issues (default: 50%)
        ALERT_POOL_UTILIZATION: % pool usage (default: 80%)

    Returns:
        Dictionary of threshold values
    """
    return {
        'degradation_threshold': get_env_float('ALERT_DEGRADATION_THRESHOLD', 25.0),
        'validation_threshold': get_env_float('ALERT_VALIDATION_THRESHOLD', 75.0),
        'timing_threshold': get_env_float('ALERT_TIMING_THRESHOLD', 50.0),
        'pool_utilization_threshold': get_env_float('ALERT_POOL_UTILIZATION', 80.0)
    }


def configure_console_handler() -> bool:
    """
    Configure console alert handler (always enabled by default)

    Environment Variables:
        ALERT_CONSOLE_ENABLED: Enable console logging (default: true)
        ALERT_CONSOLE_MIN_SEVERITY: Minimum severity (default: info)

    Returns:
        True if handler was configured
    """
    if not get_env_bool('ALERT_CONSOLE_ENABLED', True):
        return False

    try:
        from monitoring.alerts import alert_manager, AlertSeverity
        from monitoring.example_handlers import ConsoleAlertHandler

        min_severity_str = os.getenv('ALERT_CONSOLE_MIN_SEVERITY', 'info')
        min_severity = AlertSeverity(min_severity_str)

        handler = ConsoleAlertHandler(min_severity=min_severity)
        alert_manager.register_handler(handler)

        logger.info(f"✅ Console alert handler configured (min severity: {min_severity_str})")
        return True

    except Exception as e:
        logger.error(f"Failed to configure console handler: {e}")
        return False


def configure_file_handler() -> bool:
    """
    Configure file alert handler

    Environment Variables:
        ALERT_FILE_ENABLED: Enable file logging (default: true)
        ALERT_FILE_PATH: Log file path (default: logs/alerts.log)
        ALERT_FILE_MIN_SEVERITY: Minimum severity (default: warning)

    Returns:
        True if handler was configured
    """
    if not get_env_bool('ALERT_FILE_ENABLED', True):
        return False

    try:
        from monitoring.alerts import alert_manager, AlertSeverity
        from monitoring.example_handlers import FileAlertHandler

        log_path = os.getenv('ALERT_FILE_PATH', 'logs/alerts.log')
        min_severity_str = os.getenv('ALERT_FILE_MIN_SEVERITY', 'warning')
        min_severity = AlertSeverity(min_severity_str)

        # Ensure log directory exists
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        handler = FileAlertHandler(log_file=log_path, min_severity=min_severity)
        alert_manager.register_handler(handler)

        logger.info(f"✅ File alert handler configured (path: {log_path}, min severity: {min_severity_str})")
        return True

    except Exception as e:
        logger.error(f"Failed to configure file handler: {e}")
        return False


def configure_email_handler() -> bool:
    """
    Configure email alert handler

    Environment Variables:
        ALERT_EMAIL_ENABLED: Enable email alerts (default: false)
        ALERT_EMAIL_SMTP_HOST: SMTP server hostname
        ALERT_EMAIL_SMTP_PORT: SMTP server port (default: 587)
        ALERT_EMAIL_FROM: From email address
        ALERT_EMAIL_TO: To email address (comma-separated for multiple)
        ALERT_EMAIL_USERNAME: SMTP username
        ALERT_EMAIL_PASSWORD: SMTP password
        ALERT_EMAIL_USE_TLS: Use TLS (default: true)
        ALERT_EMAIL_MIN_SEVERITY: Minimum severity (default: error)

    Returns:
        True if handler was configured
    """
    if not get_env_bool('ALERT_EMAIL_ENABLED', False):
        return False

    # Check required fields
    required_vars = ['ALERT_EMAIL_SMTP_HOST', 'ALERT_EMAIL_FROM', 'ALERT_EMAIL_TO']
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        logger.warning(f"Email alerts enabled but missing variables: {', '.join(missing)}")
        return False

    try:
        from monitoring.alerts import alert_manager, AlertSeverity
        from monitoring.example_handlers import EmailAlertHandler

        smtp_host = os.getenv('ALERT_EMAIL_SMTP_HOST')
        smtp_port = get_env_int('ALERT_EMAIL_SMTP_PORT', 587)
        from_addr = os.getenv('ALERT_EMAIL_FROM')
        to_addrs = [addr.strip() for addr in os.getenv('ALERT_EMAIL_TO').split(',')]
        username = os.getenv('ALERT_EMAIL_USERNAME')
        password = os.getenv('ALERT_EMAIL_PASSWORD')
        use_tls = get_env_bool('ALERT_EMAIL_USE_TLS', True)

        min_severity_str = os.getenv('ALERT_EMAIL_MIN_SEVERITY', 'error')
        min_severity = AlertSeverity(min_severity_str)

        handler = EmailAlertHandler(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            from_addr=from_addr,
            to_addrs=to_addrs,
            username=username,
            password=password,
            use_tls=use_tls,
            min_severity=min_severity
        )
        alert_manager.register_handler(handler)

        logger.info(f"✅ Email alert handler configured (to: {', '.join(to_addrs)}, min severity: {min_severity_str})")
        return True

    except Exception as e:
        logger.error(f"Failed to configure email handler: {e}")
        return False


def configure_webhook_handler() -> bool:
    """
    Configure webhook alert handler

    Environment Variables:
        ALERT_WEBHOOK_ENABLED: Enable webhook alerts (default: false)
        ALERT_WEBHOOK_URL: Webhook URL
        ALERT_WEBHOOK_TOKEN: Optional authentication token
        ALERT_WEBHOOK_MIN_SEVERITY: Minimum severity (default: warning)

    Returns:
        True if handler was configured
    """
    if not get_env_bool('ALERT_WEBHOOK_ENABLED', False):
        return False

    webhook_url = os.getenv('ALERT_WEBHOOK_URL')
    if not webhook_url:
        logger.warning("Webhook alerts enabled but ALERT_WEBHOOK_URL not set")
        return False

    try:
        from monitoring.alerts import alert_manager, AlertSeverity
        from monitoring.example_handlers import WebhookAlertHandler

        token = os.getenv('ALERT_WEBHOOK_TOKEN')
        min_severity_str = os.getenv('ALERT_WEBHOOK_MIN_SEVERITY', 'warning')
        min_severity = AlertSeverity(min_severity_str)

        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            auth_token=token,
            min_severity=min_severity
        )
        alert_manager.register_handler(handler)

        logger.info(f"✅ Webhook alert handler configured (url: {webhook_url}, min severity: {min_severity_str})")
        return True

    except Exception as e:
        logger.error(f"Failed to configure webhook handler: {e}")
        return False


def configure_slack_handler() -> bool:
    """
    Configure Slack alert handler

    Environment Variables:
        ALERT_SLACK_ENABLED: Enable Slack alerts (default: false)
        ALERT_SLACK_WEBHOOK_URL: Slack webhook URL
        ALERT_SLACK_CHANNEL: Slack channel (default: #alerts)
        ALERT_SLACK_MIN_SEVERITY: Minimum severity (default: warning)

    Returns:
        True if handler was configured
    """
    if not get_env_bool('ALERT_SLACK_ENABLED', False):
        return False

    webhook_url = os.getenv('ALERT_SLACK_WEBHOOK_URL')
    if not webhook_url:
        logger.warning("Slack alerts enabled but ALERT_SLACK_WEBHOOK_URL not set")
        return False

    try:
        from monitoring.alerts import alert_manager, AlertSeverity
        from monitoring.example_handlers import SlackAlertHandler

        channel = os.getenv('ALERT_SLACK_CHANNEL', '#alerts')
        min_severity_str = os.getenv('ALERT_SLACK_MIN_SEVERITY', 'warning')
        min_severity = AlertSeverity(min_severity_str)

        handler = SlackAlertHandler(
            webhook_url=webhook_url,
            channel=channel,
            min_severity=min_severity
        )
        alert_manager.register_handler(handler)

        logger.info(f"✅ Slack alert handler configured (channel: {channel}, min severity: {min_severity_str})")
        return True

    except Exception as e:
        logger.error(f"Failed to configure Slack handler: {e}")
        return False


def configure_alert_thresholds():
    """Configure alert thresholds from environment"""
    try:
        from monitoring.alerts import alert_manager

        thresholds = get_alert_thresholds()

        # Update thresholds
        if 'degradation_threshold' in thresholds:
            alert_manager.set_threshold(
                'degradation_rate',
                thresholds['degradation_threshold']
            )

        if 'validation_threshold' in thresholds:
            alert_manager.set_threshold(
                'validation_rate',
                thresholds['validation_threshold']
            )

        logger.info("✅ Alert thresholds configured")
        logger.info(f"   Degradation: {thresholds['degradation_threshold']}%")
        logger.info(f"   Validation: {thresholds['validation_threshold']}%")

    except Exception as e:
        logger.error(f"Failed to configure alert thresholds: {e}")


def configure_default_alerts() -> int:
    """
    Configure default alert system based on environment

    Returns:
        Number of handlers configured
    """
    logger.info("=" * 60)
    logger.info("Configuring Alert System")
    logger.info("=" * 60)

    handlers_count = 0

    # Configure handlers
    if configure_console_handler():
        handlers_count += 1

    if configure_file_handler():
        handlers_count += 1

    if configure_email_handler():
        handlers_count += 1

    if configure_webhook_handler():
        handlers_count += 1

    if configure_slack_handler():
        handlers_count += 1

    # Configure thresholds
    configure_alert_thresholds()

    logger.info("=" * 60)
    logger.info(f"✅ Alert system configured with {handlers_count} handler(s)")
    logger.info("=" * 60)

    return handlers_count
