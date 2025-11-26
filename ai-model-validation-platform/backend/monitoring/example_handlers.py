"""Example alert handlers for email, webhook, and Slack notifications"""
import os
import logging
import smtplib
import json
from email.message import EmailMessage
from typing import Optional
from monitoring.alerts import Alert, AlertSeverity
import requests

logger = logging.getLogger(__name__)


# ============================================================================
# Email Alert Handler
# ============================================================================

class EmailAlertHandler:
    """Send email alerts using SMTP"""

    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        from_email: str = "alerts@example.com",
        to_emails: list = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        min_severity: AlertSeverity = AlertSeverity.WARNING
    ):
        """
        Initialize email alert handler

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            from_email: Sender email address
            to_emails: List of recipient email addresses
            username: SMTP authentication username
            password: SMTP authentication password
            use_tls: Whether to use TLS encryption
            min_severity: Minimum severity to send emails (default: WARNING)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_email = from_email
        self.to_emails = to_emails or []
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.min_severity = min_severity

    def __call__(self, alert: Alert):
        """Send email for alert"""
        # Filter by severity
        severity_levels = {
            AlertSeverity.INFO: 0,
            AlertSeverity.WARNING: 1,
            AlertSeverity.ERROR: 2,
            AlertSeverity.CRITICAL: 3
        }

        if severity_levels[alert.severity] < severity_levels[self.min_severity]:
            return  # Skip low severity alerts

        try:
            msg = EmailMessage()
            msg['Subject'] = f'[{alert.severity.value.upper()}] System Alert - {alert.message[:50]}'
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)

            # Compose email body
            body = f"""
System Alert Notification
========================

Severity: {alert.severity.value.upper()}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Message:
{alert.message}

Context:
{json.dumps(alert.context, indent=2)}

---
This is an automated alert from the AI Model Validation Platform
"""
            msg.set_content(body)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                if self.username and self.password:
                    server.login(self.username, self.password)

                server.send_message(msg)

            logger.info(f"📧 Email alert sent to {len(self.to_emails)} recipients")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")


# ============================================================================
# Webhook Alert Handler
# ============================================================================

class WebhookAlertHandler:
    """Send alerts to webhook endpoint"""

    def __init__(
        self,
        webhook_url: str,
        auth_token: Optional[str] = None,
        timeout: int = 5,
        min_severity: AlertSeverity = AlertSeverity.INFO
    ):
        """
        Initialize webhook alert handler

        Args:
            webhook_url: Webhook endpoint URL
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
            min_severity: Minimum severity to send (default: INFO)
        """
        self.webhook_url = webhook_url
        self.auth_token = auth_token
        self.timeout = timeout
        self.min_severity = min_severity

    def __call__(self, alert: Alert):
        """Send alert to webhook"""
        # Filter by severity
        severity_levels = {
            AlertSeverity.INFO: 0,
            AlertSeverity.WARNING: 1,
            AlertSeverity.ERROR: 2,
            AlertSeverity.CRITICAL: 3
        }

        if severity_levels[alert.severity] < severity_levels[self.min_severity]:
            return

        try:
            payload = {
                'severity': alert.severity.value,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'context': alert.context,
                'source': 'ai-model-validation-platform'
            }

            headers = {'Content-Type': 'application/json'}
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            logger.info(f"🔗 Webhook alert sent successfully (status: {response.status_code})")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send webhook alert: {e}")


# ============================================================================
# Slack Alert Handler
# ============================================================================

class SlackAlertHandler:
    """Send alerts to Slack channel"""

    def __init__(
        self,
        webhook_url: str,
        channel: Optional[str] = None,
        username: str = "Alert Bot",
        min_severity: AlertSeverity = AlertSeverity.WARNING
    ):
        """
        Initialize Slack alert handler

        Args:
            webhook_url: Slack incoming webhook URL
            channel: Optional channel override
            username: Bot username
            min_severity: Minimum severity to send (default: WARNING)
        """
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.min_severity = min_severity

    def _get_color(self, severity: AlertSeverity) -> str:
        """Get Slack color for severity"""
        colors = {
            AlertSeverity.INFO: '#36a64f',       # Green
            AlertSeverity.WARNING: '#ff9900',    # Orange
            AlertSeverity.ERROR: '#e01e5a',      # Red
            AlertSeverity.CRITICAL: '#8B0000'    # Dark Red
        }
        return colors.get(severity, '#808080')

    def _get_emoji(self, severity: AlertSeverity) -> str:
        """Get emoji for severity"""
        emojis = {
            AlertSeverity.INFO: ':information_source:',
            AlertSeverity.WARNING: ':warning:',
            AlertSeverity.ERROR: ':x:',
            AlertSeverity.CRITICAL: ':rotating_light:'
        }
        return emojis.get(severity, ':bell:')

    def __call__(self, alert: Alert):
        """Send alert to Slack"""
        # Filter by severity
        severity_levels = {
            AlertSeverity.INFO: 0,
            AlertSeverity.WARNING: 1,
            AlertSeverity.ERROR: 2,
            AlertSeverity.CRITICAL: 3
        }

        if severity_levels[alert.severity] < severity_levels[self.min_severity]:
            return

        try:
            # Format context as fields
            fields = []
            for key, value in alert.context.items():
                fields.append({
                    'title': key.replace('_', ' ').title(),
                    'value': str(value),
                    'short': True
                })

            payload = {
                'username': self.username,
                'attachments': [{
                    'color': self._get_color(alert.severity),
                    'title': f'{self._get_emoji(alert.severity)} {alert.severity.value.upper()} Alert',
                    'text': alert.message,
                    'fields': fields,
                    'footer': 'AI Model Validation Platform',
                    'ts': int(alert.timestamp.timestamp())
                }]
            }

            if self.channel:
                payload['channel'] = self.channel

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            response.raise_for_status()

            logger.info(f"💬 Slack alert sent successfully")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Slack alert: {e}")


# ============================================================================
# Factory Functions
# ============================================================================

def create_email_handler_from_env() -> Optional[EmailAlertHandler]:
    """Create email handler from environment variables

    Environment variables:
        ALERT_EMAIL_SMTP_HOST: SMTP server hostname
        ALERT_EMAIL_SMTP_PORT: SMTP server port
        ALERT_EMAIL_FROM: Sender email address
        ALERT_EMAIL_TO: Comma-separated recipient addresses
        ALERT_EMAIL_USERNAME: SMTP username
        ALERT_EMAIL_PASSWORD: SMTP password
        ALERT_EMAIL_USE_TLS: Use TLS (true/false)
        ALERT_EMAIL_MIN_SEVERITY: Minimum severity (info/warning/error/critical)
    """
    smtp_host = os.getenv('ALERT_EMAIL_SMTP_HOST')
    from_email = os.getenv('ALERT_EMAIL_FROM')
    to_emails_str = os.getenv('ALERT_EMAIL_TO')

    if not (smtp_host and from_email and to_emails_str):
        logger.debug("Email alert handler not configured (missing required env vars)")
        return None

    to_emails = [email.strip() for email in to_emails_str.split(',')]

    min_severity_str = os.getenv('ALERT_EMAIL_MIN_SEVERITY', 'warning').lower()
    min_severity = AlertSeverity(min_severity_str)

    return EmailAlertHandler(
        smtp_host=smtp_host,
        smtp_port=int(os.getenv('ALERT_EMAIL_SMTP_PORT', '587')),
        from_email=from_email,
        to_emails=to_emails,
        username=os.getenv('ALERT_EMAIL_USERNAME'),
        password=os.getenv('ALERT_EMAIL_PASSWORD'),
        use_tls=os.getenv('ALERT_EMAIL_USE_TLS', 'true').lower() == 'true',
        min_severity=min_severity
    )


def create_webhook_handler_from_env() -> Optional[WebhookAlertHandler]:
    """Create webhook handler from environment variables

    Environment variables:
        ALERT_WEBHOOK_URL: Webhook endpoint URL
        ALERT_WEBHOOK_TOKEN: Authentication token
        ALERT_WEBHOOK_MIN_SEVERITY: Minimum severity
    """
    webhook_url = os.getenv('ALERT_WEBHOOK_URL')

    if not webhook_url:
        logger.debug("Webhook alert handler not configured")
        return None

    min_severity_str = os.getenv('ALERT_WEBHOOK_MIN_SEVERITY', 'info').lower()
    min_severity = AlertSeverity(min_severity_str)

    return WebhookAlertHandler(
        webhook_url=webhook_url,
        auth_token=os.getenv('ALERT_WEBHOOK_TOKEN'),
        min_severity=min_severity
    )


def create_slack_handler_from_env() -> Optional[SlackAlertHandler]:
    """Create Slack handler from environment variables

    Environment variables:
        ALERT_SLACK_WEBHOOK_URL: Slack webhook URL
        ALERT_SLACK_CHANNEL: Channel override
        ALERT_SLACK_USERNAME: Bot username
        ALERT_SLACK_MIN_SEVERITY: Minimum severity
    """
    webhook_url = os.getenv('ALERT_SLACK_WEBHOOK_URL')

    if not webhook_url:
        logger.debug("Slack alert handler not configured")
        return None

    min_severity_str = os.getenv('ALERT_SLACK_MIN_SEVERITY', 'warning').lower()
    min_severity = AlertSeverity(min_severity_str)

    return SlackAlertHandler(
        webhook_url=webhook_url,
        channel=os.getenv('ALERT_SLACK_CHANNEL'),
        username=os.getenv('ALERT_SLACK_USERNAME', 'Alert Bot'),
        min_severity=min_severity
    )


def register_handlers_from_env():
    """Register all configured alert handlers from environment"""
    from monitoring.alerts import alert_manager

    handlers_registered = 0

    # Email handler
    email_handler = create_email_handler_from_env()
    if email_handler:
        alert_manager.register_handler(email_handler)
        handlers_registered += 1
        logger.info("✅ Email alert handler registered")

    # Webhook handler
    webhook_handler = create_webhook_handler_from_env()
    if webhook_handler:
        alert_manager.register_handler(webhook_handler)
        handlers_registered += 1
        logger.info("✅ Webhook alert handler registered")

    # Slack handler
    slack_handler = create_slack_handler_from_env()
    if slack_handler:
        alert_manager.register_handler(slack_handler)
        handlers_registered += 1
        logger.info("✅ Slack alert handler registered")

    if handlers_registered == 0:
        logger.warning("⚠️ No alert handlers configured via environment variables")
    else:
        logger.info(f"✅ Registered {handlers_registered} alert handler(s)")

    return handlers_registered
