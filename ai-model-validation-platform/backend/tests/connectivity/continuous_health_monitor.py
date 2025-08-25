#!/usr/bin/env python3
"""
Continuous Health Monitoring Script
==================================

Monitors application health continuously on both localhost and external IP.
Provides real-time status updates, alerting, and historical tracking.

Features:
- Real-time health monitoring
- Performance metrics tracking
- Alert notifications
- Historical data logging
- Dashboard status reporting
- Automated recovery suggestions

Author: AI Model Validation Platform
Date: 2025-08-24
"""

import asyncio
import json
import logging
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import threading
from pathlib import Path

try:
    import requests
    import websocket
    import socketio
    import psutil
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError as e:
    print(f"Missing dependencies. Please install: {e}")
    print("Run: pip install requests websocket-client python-socketio psutil matplotlib numpy")
    exit(1)

@dataclass
class HealthMetrics:
    """Health metrics data structure."""
    timestamp: datetime
    environment: str
    service: str
    status: str
    response_time: float
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None

class HealthMonitor:
    """Continuous health monitoring system."""
    
    def __init__(self, config_file: str = 'health_monitor_config.json'):
        self.config = self.load_config(config_file)
        self.setup_logging()
        self.metrics_history: List[HealthMetrics] = []
        self.alert_history: List[Dict] = []
        self.running = False
        self.monitor_thread = None
        
        # Health thresholds
        self.thresholds = {
            'response_time_warning': 2000,  # ms
            'response_time_critical': 5000,  # ms
            'cpu_warning': 80,  # %
            'cpu_critical': 95,  # %
            'memory_warning': 85,  # %
            'memory_critical': 95,  # %
            'disk_warning': 85,  # %
            'disk_critical': 95,  # %
            'consecutive_failures': 3
        }
        
        # Track consecutive failures
        self.failure_counts = {}
        
    def load_config(self, config_file: str) -> Dict:
        """Load monitoring configuration."""
        default_config = {
            'environments': {
                'localhost': {
                    'frontend_url': 'http://127.0.0.1:3000',
                    'backend_url': 'http://127.0.0.1:8000',
                    'websocket_url': 'ws://127.0.0.1:8000'
                },
                'external': {
                    'frontend_url': 'http://155.138.239.131:3000',
                    'backend_url': 'http://155.138.239.131:8000',
                    'websocket_url': 'ws://155.138.239.131:8000'
                }
            },
            'monitoring': {
                'interval': 60,  # seconds
                'timeout': 30,   # seconds
                'retain_history_days': 7,
                'enable_alerts': True,
                'enable_system_metrics': True
            },
            'alerts': {
                'email': {
                    'enabled': False,
                    'smtp_server': 'smtp.gmail.com',
                    'smtp_port': 587,
                    'username': '',
                    'password': '',
                    'recipients': []
                },
                'webhook': {
                    'enabled': False,
                    'url': '',
                    'headers': {}
                }
            }
        }
        
        try:
            if Path(config_file).exists():
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                # Merge with defaults
                default_config.update(loaded_config)
            else:
                # Create default config file
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                    
        except Exception as e:
            print(f"Warning: Could not load config file: {e}")
            
        return default_config
        
    def setup_logging(self):
        """Setup logging configuration."""
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('health_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def check_service_health(self, environment: str, service: str, url: str) -> HealthMetrics:
        """Check health of a specific service."""
        start_time = time.time()
        
        try:
            response = requests.get(
                url,
                timeout=self.config['monitoring']['timeout'],
                verify=False
            )
            
            response_time = (time.time() - start_time) * 1000  # ms
            
            return HealthMetrics(
                timestamp=datetime.now(),
                environment=environment,
                service=service,
                status='healthy' if response.status_code < 400 else 'degraded',
                response_time=response_time,
                status_code=response.status_code
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return HealthMetrics(
                timestamp=datetime.now(),
                environment=environment,
                service=service,
                status='unhealthy',
                response_time=response_time,
                error_message=str(e)
            )
            
    def check_websocket_health(self, environment: str, ws_url: str) -> HealthMetrics:
        """Check WebSocket health."""
        start_time = time.time()
        
        try:
            ws = websocket.create_connection(
                ws_url,
                timeout=self.config['monitoring']['timeout']
            )
            ws.close()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthMetrics(
                timestamp=datetime.now(),
                environment=environment,
                service='websocket',
                status='healthy',
                response_time=response_time
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return HealthMetrics(
                timestamp=datetime.now(),
                environment=environment,
                service='websocket',
                status='unhealthy',
                response_time=response_time,
                error_message=str(e)
            )
            
    def get_system_metrics(self) -> Dict[str, float]:
        """Get system resource metrics."""
        if not self.config['monitoring']['enable_system_metrics']:
            return {}
            
        try:
            return {
                'cpu_usage': psutil.cpu_percent(interval=1),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent
            }
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")
            return {}
            
    async def run_health_checks(self) -> List[HealthMetrics]:
        """Run all health checks for all environments."""
        metrics = []
        system_metrics = self.get_system_metrics()
        
        for env_name, env_config in self.config['environments'].items():
            # Check frontend
            frontend_metrics = self.check_service_health(
                env_name, 'frontend', env_config['frontend_url']
            )
            frontend_metrics.cpu_usage = system_metrics.get('cpu_usage')
            frontend_metrics.memory_usage = system_metrics.get('memory_usage')
            frontend_metrics.disk_usage = system_metrics.get('disk_usage')
            metrics.append(frontend_metrics)
            
            # Check backend
            backend_metrics = self.check_service_health(
                env_name, 'backend', f"{env_config['backend_url']}/health"
            )
            backend_metrics.cpu_usage = system_metrics.get('cpu_usage')
            backend_metrics.memory_usage = system_metrics.get('memory_usage')
            backend_metrics.disk_usage = system_metrics.get('disk_usage')
            metrics.append(backend_metrics)
            
            # Check WebSocket
            ws_metrics = self.check_websocket_health(
                env_name, env_config['websocket_url']
            )
            ws_metrics.cpu_usage = system_metrics.get('cpu_usage')
            ws_metrics.memory_usage = system_metrics.get('memory_usage')
            ws_metrics.disk_usage = system_metrics.get('disk_usage')
            metrics.append(ws_metrics)
            
            # Small delay between environments
            await asyncio.sleep(0.5)
            
        return metrics
        
    def analyze_metrics(self, metrics: List[HealthMetrics]) -> Dict[str, Any]:
        """Analyze metrics and determine overall health."""
        analysis = {
            'overall_status': 'healthy',
            'unhealthy_services': [],
            'performance_issues': [],
            'system_issues': [],
            'alerts': []
        }
        
        for metric in metrics:
            service_key = f"{metric.environment}-{metric.service}"
            
            # Track consecutive failures
            if metric.status == 'unhealthy':
                self.failure_counts[service_key] = self.failure_counts.get(service_key, 0) + 1
            else:
                self.failure_counts[service_key] = 0
                
            # Check service health
            if metric.status == 'unhealthy':
                analysis['unhealthy_services'].append({
                    'environment': metric.environment,
                    'service': metric.service,
                    'error': metric.error_message,
                    'consecutive_failures': self.failure_counts[service_key]
                })
                analysis['overall_status'] = 'degraded'
                
                # Critical alert for consecutive failures
                if self.failure_counts[service_key] >= self.thresholds['consecutive_failures']:
                    analysis['alerts'].append({
                        'level': 'critical',
                        'message': f"{metric.environment} {metric.service} has failed {self.failure_counts[service_key]} times consecutively",
                        'service': service_key
                    })
                    analysis['overall_status'] = 'critical'
                    
            # Check performance
            if metric.response_time > self.thresholds['response_time_critical']:
                analysis['performance_issues'].append({
                    'environment': metric.environment,
                    'service': metric.service,
                    'response_time': metric.response_time,
                    'level': 'critical'
                })
                analysis['alerts'].append({
                    'level': 'critical',
                    'message': f"{metric.environment} {metric.service} response time critical: {metric.response_time:.0f}ms",
                    'service': service_key
                })
                
            elif metric.response_time > self.thresholds['response_time_warning']:
                analysis['performance_issues'].append({
                    'environment': metric.environment,
                    'service': metric.service,
                    'response_time': metric.response_time,
                    'level': 'warning'
                })
                
            # Check system resources
            for resource, value in [
                ('cpu_usage', metric.cpu_usage),
                ('memory_usage', metric.memory_usage),
                ('disk_usage', metric.disk_usage)
            ]:
                if value is not None:
                    if value > self.thresholds[f"{resource.split('_')[0]}_critical"]:
                        analysis['system_issues'].append({
                            'resource': resource,
                            'value': value,
                            'level': 'critical'
                        })
                        analysis['alerts'].append({
                            'level': 'critical',
                            'message': f"System {resource} critical: {value:.1f}%",
                            'service': 'system'
                        })
                        
                    elif value > self.thresholds[f"{resource.split('_')[0]}_warning"]:
                        analysis['system_issues'].append({
                            'resource': resource,
                            'value': value,
                            'level': 'warning'
                        })
                        
        return analysis
        
    async def send_alert(self, alert: Dict[str, Any]):
        """Send alert notification."""
        if not self.config['monitoring']['enable_alerts']:
            return
            
        # Email alerts
        email_config = self.config['alerts']['email']
        if email_config['enabled'] and email_config['recipients']:
            await self.send_email_alert(alert, email_config)
            
        # Webhook alerts
        webhook_config = self.config['alerts']['webhook']
        if webhook_config['enabled'] and webhook_config['url']:
            await self.send_webhook_alert(alert, webhook_config)
            
    async def send_email_alert(self, alert: Dict[str, Any], email_config: Dict[str, Any]):
        """Send email alert."""
        try:
            msg = MIMEMultipart()
            msg['From'] = email_config['username']
            msg['To'] = ', '.join(email_config['recipients'])
            msg['Subject'] = f"AI Validation Platform Alert - {alert['level'].upper()}"
            
            body = f"""
            Alert Level: {alert['level'].upper()}
            Service: {alert['service']}
            Message: {alert['message']}
            Timestamp: {datetime.now().isoformat()}
            
            This is an automated alert from the AI Model Validation Platform health monitor.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['username'], email_config['password'])
            
            text = msg.as_string()
            server.sendmail(email_config['username'], email_config['recipients'], text)
            server.quit()
            
            self.logger.info(f"Email alert sent: {alert['message']}")
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            
    async def send_webhook_alert(self, alert: Dict[str, Any], webhook_config: Dict[str, Any]):
        """Send webhook alert."""
        try:
            payload = {
                'level': alert['level'],
                'service': alert['service'],
                'message': alert['message'],
                'timestamp': datetime.now().isoformat(),
                'source': 'AI-Validation-Health-Monitor'
            }
            
            response = requests.post(
                webhook_config['url'],
                json=payload,
                headers=webhook_config.get('headers', {}),
                timeout=10
            )
            
            if response.status_code < 400:
                self.logger.info(f"Webhook alert sent: {alert['message']}")
            else:
                self.logger.error(f"Webhook alert failed: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
            
    def save_metrics(self, metrics: List[HealthMetrics]):
        """Save metrics to file."""
        try:
            # Convert to serializable format
            serializable_metrics = [
                {
                    **asdict(metric),
                    'timestamp': metric.timestamp.isoformat()
                }
                for metric in metrics
            ]
            
            # Save to JSON file with timestamp
            filename = f"health_metrics_{datetime.now().strftime('%Y%m%d')}.json"
            
            # Load existing data
            existing_data = []
            if Path(filename).exists():
                with open(filename, 'r') as f:
                    existing_data = json.load(f)
                    
            # Append new metrics
            existing_data.extend(serializable_metrics)
            
            # Save updated data
            with open(filename, 'w') as f:
                json.dump(existing_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save metrics: {e}")
            
    def cleanup_old_metrics(self):
        """Clean up old metric files."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config['monitoring']['retain_history_days'])
            
            for file_path in Path('.').glob('health_metrics_*.json'):
                try:
                    # Extract date from filename
                    date_str = file_path.stem.split('_')[-1]
                    file_date = datetime.strptime(date_str, '%Y%m%d')
                    
                    if file_date < cutoff_date:
                        file_path.unlink()
                        self.logger.info(f"Removed old metrics file: {file_path}")
                        
                except (ValueError, IndexError):
                    # Skip files with invalid date format
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up old metrics: {e}")
            
    def generate_status_dashboard(self, analysis: Dict[str, Any]) -> str:
        """Generate ASCII status dashboard."""
        dashboard_lines = [
            "=" * 80,
            "AI MODEL VALIDATION PLATFORM - HEALTH DASHBOARD",
            "=" * 80,
            f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Overall Status: {self.get_status_emoji(analysis['overall_status'])} {analysis['overall_status'].upper()}",
            ""
        ]
        
        # Service Status Grid
        dashboard_lines.extend([
            "SERVICE STATUS",
            "-" * 40,
            ""
        ])
        
        # Get latest metrics by service
        latest_metrics = {}
        for metric in self.metrics_history[-6:]:  # Last 6 checks (2 environments × 3 services)
            key = f"{metric.environment}-{metric.service}"
            latest_metrics[key] = metric
            
        # Display in grid format
        environments = ['localhost', 'external']
        services = ['frontend', 'backend', 'websocket']
        
        header = "Service".ljust(15)
        for env in environments:
            header += f"{env.capitalize()}".ljust(15)
        dashboard_lines.append(header)
        dashboard_lines.append("-" * len(header))
        
        for service in services:
            line = service.capitalize().ljust(15)
            for env in environments:
                key = f"{env}-{service}"
                if key in latest_metrics:
                    metric = latest_metrics[key]
                    status_emoji = self.get_status_emoji(metric.status)
                    response_time = f"({metric.response_time:.0f}ms)" if metric.response_time else ""
                    line += f"{status_emoji} {metric.status}".ljust(15)
                else:
                    line += "❓ unknown".ljust(15)
            dashboard_lines.append(line)
            
        dashboard_lines.append("")
        
        # System Resources
        if self.config['monitoring']['enable_system_metrics'] and self.metrics_history:
            latest_metric = self.metrics_history[-1]
            if any([latest_metric.cpu_usage, latest_metric.memory_usage, latest_metric.disk_usage]):
                dashboard_lines.extend([
                    "SYSTEM RESOURCES",
                    "-" * 40,
                    ""
                ])
                
                if latest_metric.cpu_usage is not None:
                    cpu_bar = self.create_progress_bar(latest_metric.cpu_usage, 100)
                    dashboard_lines.append(f"CPU Usage:    {cpu_bar} {latest_metric.cpu_usage:.1f}%")
                    
                if latest_metric.memory_usage is not None:
                    mem_bar = self.create_progress_bar(latest_metric.memory_usage, 100)
                    dashboard_lines.append(f"Memory Usage: {mem_bar} {latest_metric.memory_usage:.1f}%")
                    
                if latest_metric.disk_usage is not None:
                    disk_bar = self.create_progress_bar(latest_metric.disk_usage, 100)
                    dashboard_lines.append(f"Disk Usage:   {disk_bar} {latest_metric.disk_usage:.1f}%")
                    
                dashboard_lines.append("")
                
        # Alerts
        if analysis['alerts']:
            dashboard_lines.extend([
                "ACTIVE ALERTS",
                "-" * 40,
                ""
            ])
            
            for alert in analysis['alerts'][-5:]:  # Show last 5 alerts
                level_emoji = "🚨" if alert['level'] == 'critical' else "⚠️"
                dashboard_lines.append(f"{level_emoji} {alert['message']}")
                
            dashboard_lines.append("")
            
        # Performance Issues
        if analysis['performance_issues']:
            dashboard_lines.extend([
                "PERFORMANCE ISSUES",
                "-" * 40,
                ""
            ])
            
            for issue in analysis['performance_issues'][-5:]:
                level_emoji = "🚨" if issue['level'] == 'critical' else "⚠️"
                dashboard_lines.append(
                    f"{level_emoji} {issue['environment']} {issue['service']}: {issue['response_time']:.0f}ms"
                )
                
            dashboard_lines.append("")
            
        dashboard_lines.extend([
            "=" * 80,
            f"Next check in {self.config['monitoring']['interval']} seconds",
            "=" * 80
        ])
        
        return "\n".join(dashboard_lines)
        
    def get_status_emoji(self, status: str) -> str:
        """Get emoji for status."""
        status_emojis = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌',
            'critical': '🚨'
        }
        return status_emojis.get(status, '❓')
        
    def create_progress_bar(self, value: float, max_value: float, width: int = 20) -> str:
        """Create ASCII progress bar."""
        percentage = min(value / max_value, 1.0)
        filled = int(width * percentage)
        bar = '█' * filled + '░' * (width - filled)
        
        # Color coding based on thresholds
        if value > self.thresholds.get(f"{max_value}_critical", 95):
            return f"🔴{bar}"
        elif value > self.thresholds.get(f"{max_value}_warning", 80):
            return f"🟡{bar}"
        else:
            return f"🟢{bar}"
            
    async def monitoring_loop(self):
        """Main monitoring loop."""
        self.logger.info("🚀 Starting health monitoring loop")
        
        while self.running:
            try:
                # Run health checks
                metrics = await self.run_health_checks()
                
                # Add to history
                self.metrics_history.extend(metrics)
                
                # Keep only recent history (last 24 hours)
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history 
                    if m.timestamp > cutoff_time
                ]
                
                # Analyze metrics
                analysis = self.analyze_metrics(metrics)
                
                # Send alerts if needed
                for alert in analysis['alerts']:
                    # Check if this alert was already sent recently
                    recent_alerts = [
                        a for a in self.alert_history 
                        if datetime.fromisoformat(a['timestamp']) > datetime.now() - timedelta(minutes=30)
                    ]
                    
                    alert_key = f"{alert['level']}-{alert['service']}"
                    if not any(a.get('key') == alert_key for a in recent_alerts):
                        await self.send_alert(alert)
                        self.alert_history.append({
                            'key': alert_key,
                            'timestamp': datetime.now().isoformat(),
                            **alert
                        })
                        
                # Save metrics
                self.save_metrics(metrics)
                
                # Generate and display dashboard
                dashboard = self.generate_status_dashboard(analysis)
                
                # Clear screen and display dashboard
                os.system('clear' if os.name == 'posix' else 'cls')
                print(dashboard)
                
                # Log summary
                healthy_services = len([m for m in metrics if m.status == 'healthy'])
                total_services = len(metrics)
                self.logger.info(f"Health check completed: {healthy_services}/{total_services} services healthy")
                
                # Cleanup old metrics daily
                if datetime.now().hour == 0 and datetime.now().minute < 5:
                    self.cleanup_old_metrics()
                    
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                
            # Wait for next check
            await asyncio.sleep(self.config['monitoring']['interval'])
            
    def start_monitoring(self):
        """Start the monitoring service."""
        if self.running:
            self.logger.warning("Monitoring is already running")
            return
            
        self.running = True
        self.logger.info("Starting continuous health monitoring")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Start monitoring loop
        asyncio.run(self.monitoring_loop())
        
    def stop_monitoring(self):
        """Stop the monitoring service."""
        self.running = False
        self.logger.info("Stopping health monitoring")
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop_monitoring()
        sys.exit(0)
        
    def generate_historical_report(self, hours: int = 24) -> str:
        """Generate historical health report."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history 
            if m.timestamp > cutoff_time
        ]
        
        if not recent_metrics:
            return "No historical data available"
            
        # Calculate availability
        availability_stats = {}
        for metric in recent_metrics:
            key = f"{metric.environment}-{metric.service}"
            if key not in availability_stats:
                availability_stats[key] = {'total': 0, 'healthy': 0}
                
            availability_stats[key]['total'] += 1
            if metric.status == 'healthy':
                availability_stats[key]['healthy'] += 1
                
        report_lines = [
            "=" * 80,
            f"HEALTH REPORT - LAST {hours} HOURS",
            "=" * 80,
            f"Generated: {datetime.now().isoformat()}",
            f"Metrics Analyzed: {len(recent_metrics)}",
            ""
        ]
        
        # Availability Report
        report_lines.extend([
            "SERVICE AVAILABILITY",
            "-" * 40,
            ""
        ])
        
        for service_key, stats in availability_stats.items():
            availability = (stats['healthy'] / stats['total']) * 100
            status_emoji = '✅' if availability >= 99 else '⚠️' if availability >= 95 else '❌'
            report_lines.append(f"{status_emoji} {service_key}: {availability:.2f}% ({stats['healthy']}/{stats['total']})")
            
        return "\n".join(report_lines)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Model Validation Platform Health Monitor')
    parser.add_argument('--config', default='health_monitor_config.json', help='Configuration file path')
    parser.add_argument('--interval', type=int, help='Monitoring interval in seconds')
    parser.add_argument('--report', type=int, help='Generate historical report for N hours')
    
    args = parser.parse_args()
    
    monitor = HealthMonitor(args.config)
    
    # Override interval if specified
    if args.interval:
        monitor.config['monitoring']['interval'] = args.interval
        
    if args.report:
        # Generate historical report
        report = monitor.generate_historical_report(args.report)
        print(report)
    else:
        # Start continuous monitoring
        try:
            monitor.start_monitoring()
        except KeyboardInterrupt:
            monitor.stop_monitoring()
            print("\nHealth monitoring stopped.")


if __name__ == "__main__":
    main()