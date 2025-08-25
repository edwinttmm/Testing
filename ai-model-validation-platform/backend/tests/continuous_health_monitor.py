#!/usr/bin/env python3
"""
Continuous Health Monitoring Daemon for Database Connectivity

A comprehensive monitoring system that continuously watches database health,
connectivity, and performance metrics with real-time alerting and recovery.

Features:
- Continuous database health monitoring
- Real-time performance metrics collection
- Automated alert generation and escalation
- Self-healing capabilities for common issues
- Historical trend analysis
- Dashboard and reporting integration
- Configurable monitoring intervals and thresholds
"""

import os
import sys
import json
import time
import signal
import logging
import threading
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from collections import deque
import statistics

# Add backend directory to path
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')

try:
    import psutil
    from db_health_check import PostgreSQLHealthChecker
    from network_connectivity_test import NetworkConnectivityTester
    from database_connection_validator import DatabaseConnectionValidator
    from database_init_verifier import DatabaseInitializationVerifier
except ImportError as e:
    print(f"Warning: Some monitoring modules unavailable: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/home/user/Testing/ai-model-validation-platform/backend/logs/health_monitor.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class HealthMetric:
    """Health metric data structure"""
    timestamp: str
    component: str
    metric_name: str
    value: float
    status: str  # 'healthy', 'warning', 'critical'
    threshold_exceeded: bool
    details: Dict[str, Any]

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    timestamp: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    component: str
    message: str
    details: Dict[str, Any]
    acknowledged: bool = False
    resolved: bool = False
    resolution_timestamp: Optional[str] = None

class HealthTrendAnalyzer:
    """Analyze health trends and predict issues"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metric_history = {}
        self.trend_alerts = []
    
    def add_metric(self, metric: HealthMetric) -> None:
        """Add metric to history for trend analysis"""
        key = f"{metric.component}_{metric.metric_name}"
        
        if key not in self.metric_history:
            self.metric_history[key] = deque(maxlen=self.window_size)
        
        self.metric_history[key].append({
            'timestamp': metric.timestamp,
            'value': metric.value,
            'status': metric.status
        })
    
    def analyze_trends(self) -> List[Dict[str, Any]]:
        """Analyze trends and identify concerning patterns"""
        trend_analysis = []
        
        for key, history in self.metric_history.items():
            if len(history) < 10:  # Need at least 10 data points
                continue
            
            values = [item['value'] for item in history]
            timestamps = [datetime.fromisoformat(item['timestamp']) for item in history]
            
            # Calculate trend metrics
            try:
                # Linear regression for trend direction
                n = len(values)
                sum_x = sum(range(n))
                sum_y = sum(values)
                sum_xy = sum(i * values[i] for i in range(n))
                sum_x2 = sum(i * i for i in range(n))
                
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                
                # Statistical measures
                mean_value = statistics.mean(values)
                std_dev = statistics.stdev(values) if len(values) > 1 else 0
                recent_mean = statistics.mean(values[-5:])  # Last 5 values
                
                # Volatility (coefficient of variation)
                volatility = (std_dev / mean_value) * 100 if mean_value != 0 else 0
                
                # Trend classification
                trend_direction = 'stable'
                if abs(slope) > std_dev * 0.1:  # Significant trend
                    trend_direction = 'increasing' if slope > 0 else 'decreasing'
                
                # Anomaly detection - values outside 2 std deviations
                anomalies = sum(1 for v in values[-10:] if abs(v - mean_value) > 2 * std_dev)
                anomaly_rate = (anomalies / min(10, len(values))) * 100
                
                trend_analysis.append({
                    'metric': key,
                    'trend_direction': trend_direction,
                    'slope': round(slope, 4),
                    'mean_value': round(mean_value, 2),
                    'recent_mean': round(recent_mean, 2),
                    'std_deviation': round(std_dev, 2),
                    'volatility_percent': round(volatility, 1),
                    'anomaly_rate_percent': round(anomaly_rate, 1),
                    'data_points': len(values),
                    'time_span_minutes': (timestamps[-1] - timestamps[0]).total_seconds() / 60,
                    'concerning_trend': self._is_concerning_trend(slope, std_dev, anomaly_rate, volatility)
                })
                
            except (ZeroDivisionError, ValueError, statistics.StatisticsError) as e:
                logger.warning(f"Trend analysis failed for {key}: {e}")
        
        return trend_analysis
    
    def _is_concerning_trend(self, slope: float, std_dev: float, anomaly_rate: float, volatility: float) -> bool:
        """Determine if a trend is concerning"""
        return (
            abs(slope) > std_dev * 0.2 or  # Significant trend
            anomaly_rate > 20 or  # High anomaly rate
            volatility > 50  # High volatility
        )

class AlertManager:
    """Manage alerts, escalation, and notifications"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.alerts = deque(maxlen=1000)  # Keep last 1000 alerts
        self.alert_handlers = {}
        self.escalation_rules = config.get('escalation_rules', {})
        self.notification_queue = Queue()
    
    def register_alert_handler(self, severity: str, handler: Callable) -> None:
        """Register alert handler for specific severity"""
        if severity not in self.alert_handlers:
            self.alert_handlers[severity] = []
        self.alert_handlers[severity].append(handler)
    
    def create_alert(self, component: str, message: str, severity: str, details: Dict = None) -> Alert:
        """Create new alert"""
        alert = Alert(
            id=f"{int(time.time())}_{component}_{hash(message) % 10000}",
            timestamp=datetime.now().isoformat(),
            severity=severity,
            component=component,
            message=message,
            details=details or {},
            acknowledged=False,
            resolved=False
        )
        
        self.alerts.append(alert)
        self._process_alert(alert)
        
        return alert
    
    def _process_alert(self, alert: Alert) -> None:
        """Process alert through handlers and escalation"""
        logger.warning(f"ALERT [{alert.severity.upper()}] {alert.component}: {alert.message}")
        
        # Call registered handlers
        handlers = self.alert_handlers.get(alert.severity, [])
        for handler in handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
        
        # Add to notification queue
        self.notification_queue.put(alert)
        
        # Check for escalation
        self._check_escalation(alert)
    
    def _check_escalation(self, alert: Alert) -> None:
        """Check if alert needs escalation"""
        escalation_rules = self.escalation_rules.get(alert.severity, {})
        
        if not escalation_rules:
            return
        
        # Simple escalation: if critical alerts persist
        if alert.severity == 'critical':
            recent_criticals = [
                a for a in self.alerts
                if a.component == alert.component and 
                   a.severity == 'critical' and 
                   not a.resolved and
                   (datetime.now() - datetime.fromisoformat(a.timestamp)).total_seconds() < 300  # Last 5 minutes
            ]
            
            if len(recent_criticals) >= escalation_rules.get('count_threshold', 3):
                escalated_alert = self.create_alert(
                    component='system',
                    message=f"ESCALATED: Multiple critical alerts for {alert.component}",
                    severity='critical',
                    details={
                        'escalated_from': alert.id,
                        'alert_count': len(recent_criticals),
                        'original_alerts': [a.id for a in recent_criticals]
                    }
                )
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert {alert_id} acknowledged")
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                alert.resolution_timestamp = datetime.now().isoformat()
                logger.info(f"Alert {alert_id} resolved")
                return True
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all unresolved alerts"""
        return [alert for alert in self.alerts if not alert.resolved]

class ContinuousHealthMonitor:
    """Main continuous health monitoring system"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._load_default_config()
        self.running = False
        self.monitoring_thread = None
        self.alert_manager = AlertManager(self.config)
        self.trend_analyzer = HealthTrendAnalyzer()
        self.health_checkers = self._initialize_health_checkers()
        self.metrics_history = deque(maxlen=10000)  # Keep last 10k metrics
        self.last_health_status = {}
        self.performance_baselines = {}
        
        # Performance tracking
        self.monitoring_stats = {
            'checks_performed': 0,
            'alerts_generated': 0,
            'self_healings_attempted': 0,
            'uptime_start': datetime.now().isoformat()
        }
        
        # Register default alert handlers
        self._register_default_handlers()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _load_default_config(self) -> Dict:
        """Load default monitoring configuration"""
        return {
            'monitoring_interval': 30,  # seconds
            'alert_cooldown': 300,  # 5 minutes between same alerts
            'health_checks': {
                'postgres_health': {
                    'enabled': True,
                    'interval_multiplier': 1,  # Run every monitoring_interval
                    'thresholds': {
                        'connection_time_ms': {'warning': 1000, 'critical': 5000},
                        'pool_usage_percent': {'warning': 80, 'critical': 95},
                        'failed_connections_percent': {'warning': 5, 'critical': 20}
                    }
                },
                'network_connectivity': {
                    'enabled': True,
                    'interval_multiplier': 2,  # Run every 2 * monitoring_interval
                    'thresholds': {
                        'success_rate_percent': {'warning': 90, 'critical': 70},
                        'average_latency_ms': {'warning': 500, 'critical': 2000}
                    }
                },
                'database_connection': {
                    'enabled': True,
                    'interval_multiplier': 1,
                    'thresholds': {
                        'success_rate_percent': {'warning': 95, 'critical': 80},
                        'average_duration_ms': {'warning': 200, 'critical': 1000}
                    }
                },
                'database_schema': {
                    'enabled': True,
                    'interval_multiplier': 10,  # Run every 10 * monitoring_interval
                    'thresholds': {
                        'missing_tables_count': {'warning': 1, 'critical': 3},
                        'schema_integrity_percent': {'warning': 95, 'critical': 80}
                    }
                },
                'system_resources': {
                    'enabled': True,
                    'interval_multiplier': 1,
                    'thresholds': {
                        'cpu_usage_percent': {'warning': 80, 'critical': 95},
                        'memory_usage_percent': {'warning': 85, 'critical': 95},
                        'disk_usage_percent': {'warning': 90, 'critical': 95}
                    }
                }
            },
            'escalation_rules': {
                'critical': {
                    'count_threshold': 3,
                    'time_window_minutes': 5
                }
            },
            'self_healing': {
                'enabled': True,
                'max_attempts': 3,
                'cooldown_minutes': 10,
                'actions': {
                    'restart_containers': True,
                    'recreate_connections': True,
                    'reinitialize_schema': True
                }
            },
            'data_retention': {
                'metrics_days': 7,
                'alerts_days': 30,
                'logs_days': 14
            },
            'notifications': {
                'enabled': False,  # Disable external notifications by default
                'email': {
                    'enabled': False,
                    'recipients': [],
                    'smtp_server': '',
                    'severity_threshold': 'high'
                },
                'webhook': {
                    'enabled': False,
                    'url': '',
                    'severity_threshold': 'critical'
                }
            }
        }
    
    def _initialize_health_checkers(self) -> Dict:
        """Initialize all health checker instances"""
        checkers = {}
        
        try:
            checkers['postgres'] = PostgreSQLHealthChecker()
        except Exception as e:
            logger.warning(f"Could not initialize PostgreSQL health checker: {e}")
        
        try:
            checkers['network'] = NetworkConnectivityTester()
        except Exception as e:
            logger.warning(f"Could not initialize network connectivity tester: {e}")
        
        try:
            checkers['database'] = DatabaseConnectionValidator()
        except Exception as e:
            logger.warning(f"Could not initialize database connection validator: {e}")
        
        try:
            checkers['schema'] = DatabaseInitializationVerifier()
        except Exception as e:
            logger.warning(f"Could not initialize database schema verifier: {e}")
        
        return checkers
    
    def _register_default_handlers(self) -> None:
        """Register default alert handlers"""
        self.alert_manager.register_alert_handler('critical', self._handle_critical_alert)
        self.alert_manager.register_alert_handler('high', self._handle_high_alert)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop_monitoring()
    
    def _handle_critical_alert(self, alert: Alert) -> None:
        """Handle critical alerts with self-healing attempts"""
        if not self.config['self_healing']['enabled']:
            return
        
        healing_actions = {
            'postgres_container': self._heal_postgres_container,
            'database_connection': self._heal_database_connection,
            'network_connectivity': self._heal_network_connectivity,
            'database_schema': self._heal_database_schema
        }
        
        action = healing_actions.get(alert.component)
        if action:
            try:
                logger.info(f"Attempting self-healing for {alert.component}")
                success = action(alert)
                
                if success:
                    self.alert_manager.resolve_alert(alert.id)
                    self.monitoring_stats['self_healings_attempted'] += 1
                    logger.info(f"Self-healing successful for {alert.component}")
                else:
                    logger.warning(f"Self-healing failed for {alert.component}")
            except Exception as e:
                logger.error(f"Self-healing crashed for {alert.component}: {e}")
    
    def _handle_high_alert(self, alert: Alert) -> None:
        """Handle high priority alerts"""
        # For high alerts, just log and monitor
        logger.warning(f"High priority alert requires attention: {alert.component} - {alert.message}")
    
    def _heal_postgres_container(self, alert: Alert) -> bool:
        """Attempt to heal PostgreSQL container issues"""
        try:
            import subprocess
            
            # Check container status
            result = subprocess.run(
                ['docker-compose', 'ps', 'postgres'],
                cwd='/home/user/Testing/ai-model-validation-platform',
                capture_output=True,
                text=True
            )
            
            if 'Up' not in result.stdout:
                # Container is down, try to restart
                restart_result = subprocess.run(
                    ['docker-compose', 'restart', 'postgres'],
                    cwd='/home/user/Testing/ai-model-validation-platform',
                    capture_output=True,
                    text=True
                )
                
                return restart_result.returncode == 0
            
            return True
            
        except Exception as e:
            logger.error(f"PostgreSQL container healing failed: {e}")
            return False
    
    def _heal_database_connection(self, alert: Alert) -> bool:
        """Attempt to heal database connection issues"""
        try:
            # Simple connection retry
            if 'database' in self.health_checkers:
                validator = self.health_checkers['database']
                result = validator.test_sqlalchemy_connection()
                return result.success
            return False
        except Exception as e:
            logger.error(f"Database connection healing failed: {e}")
            return False
    
    def _heal_network_connectivity(self, alert: Alert) -> bool:
        """Attempt to heal network connectivity issues"""
        try:
            # Test network connectivity and return status
            if 'network' in self.health_checkers:
                tester = self.health_checkers['network']
                results = tester.test_service_health('postgres')
                return results.success
            return False
        except Exception as e:
            logger.error(f"Network connectivity healing failed: {e}")
            return False
    
    def _heal_database_schema(self, alert: Alert) -> bool:
        """Attempt to heal database schema issues"""
        try:
            if 'schema' in self.health_checkers:
                verifier = self.health_checkers['schema']
                result = verifier.initialize_database_schema()
                return result['success']
            return False
        except Exception as e:
            logger.error(f"Database schema healing failed: {e}")
            return False
    
    def check_system_resources(self) -> Dict[str, HealthMetric]:
        """Check system resource usage"""
        metrics = {}
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = self._determine_status(cpu_percent, 
                self.config['health_checks']['system_resources']['thresholds']['cpu_usage_percent'])
            
            metrics['cpu_usage'] = HealthMetric(
                timestamp=datetime.now().isoformat(),
                component='system_resources',
                metric_name='cpu_usage_percent',
                value=cpu_percent,
                status=cpu_status,
                threshold_exceeded=cpu_status != 'healthy',
                details={'cores': psutil.cpu_count()}
            )
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_status = self._determine_status(memory.percent,
                self.config['health_checks']['system_resources']['thresholds']['memory_usage_percent'])
            
            metrics['memory_usage'] = HealthMetric(
                timestamp=datetime.now().isoformat(),
                component='system_resources',
                metric_name='memory_usage_percent',
                value=memory.percent,
                status=memory_status,
                threshold_exceeded=memory_status != 'healthy',
                details={
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2)
                }
            )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_status = self._determine_status(disk_percent,
                self.config['health_checks']['system_resources']['thresholds']['disk_usage_percent'])
            
            metrics['disk_usage'] = HealthMetric(
                timestamp=datetime.now().isoformat(),
                component='system_resources',
                metric_name='disk_usage_percent',
                value=disk_percent,
                status=disk_status,
                threshold_exceeded=disk_status != 'healthy',
                details={
                    'total_gb': round(disk.total / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2)
                }
            )
            
        except Exception as e:
            logger.error(f"System resource check failed: {e}")
        
        return metrics
    
    def _determine_status(self, value: float, thresholds: Dict) -> str:
        """Determine status based on value and thresholds"""
        if value >= thresholds.get('critical', float('inf')):
            return 'critical'
        elif value >= thresholds.get('warning', float('inf')):
            return 'warning'
        else:
            return 'healthy'
    
    def run_health_checks(self, iteration: int) -> Dict[str, Any]:
        """Run all enabled health checks"""
        check_results = {}
        metrics_collected = []
        
        health_config = self.config['health_checks']
        
        # PostgreSQL Health Check
        if (health_config['postgres_health']['enabled'] and 
            iteration % health_config['postgres_health']['interval_multiplier'] == 0):
            
            if 'postgres' in self.health_checkers:
                try:
                    postgres_results = self.health_checkers['postgres'].run_comprehensive_health_check()
                    check_results['postgres_health'] = postgres_results
                    
                    # Extract metrics and check thresholds
                    for component, result in postgres_results.items():
                        if hasattr(result, 'status'):
                            metric = HealthMetric(
                                timestamp=datetime.now().isoformat(),
                                component='postgres_health',
                                metric_name=component,
                                value=1.0 if result.status == 'healthy' else 0.0,
                                status=result.status,
                                threshold_exceeded=result.status not in ['healthy'],
                                details=asdict(result)
                            )
                            metrics_collected.append(metric)
                            
                            # Check for alerts
                            if result.status == 'error':
                                self.alert_manager.create_alert(
                                    component='postgres_container',
                                    message=f"PostgreSQL health check failed: {result.error}",
                                    severity='critical',
                                    details=asdict(result)
                                )
                            elif result.status == 'unhealthy':
                                self.alert_manager.create_alert(
                                    component='postgres_container',
                                    message=f"PostgreSQL health degraded: {component}",
                                    severity='high',
                                    details=asdict(result)
                                )
                    
                except Exception as e:
                    logger.error(f"PostgreSQL health check failed: {e}")
                    check_results['postgres_health'] = {'error': str(e)}
        
        # Network Connectivity Check
        if (health_config['network_connectivity']['enabled'] and
            iteration % health_config['network_connectivity']['interval_multiplier'] == 0):
            
            if 'network' in self.health_checkers:
                try:
                    network_results = self.health_checkers['network'].run_comprehensive_network_test()
                    check_results['network_connectivity'] = network_results
                    
                    # Extract key metrics
                    success_rate = network_results.get('successful_tests', 0) / max(network_results.get('total_tests', 1), 1) * 100
                    avg_latency = network_results.get('average_latency_ms', 0)
                    
                    success_status = self._determine_status(100 - success_rate,  # Invert for threshold comparison
                        {'warning': 10, 'critical': 30})  # 90% success = 10% failure
                    latency_status = self._determine_status(avg_latency,
                        health_config['network_connectivity']['thresholds']['average_latency_ms'])
                    
                    overall_status = 'critical' if 'critical' in [success_status, latency_status] else (
                        'warning' if 'warning' in [success_status, latency_status] else 'healthy'
                    )
                    
                    metric = HealthMetric(
                        timestamp=datetime.now().isoformat(),
                        component='network_connectivity',
                        metric_name='overall_health',
                        value=success_rate,
                        status=overall_status,
                        threshold_exceeded=overall_status != 'healthy',
                        details=network_results
                    )
                    metrics_collected.append(metric)
                    
                    # Check for alerts
                    if success_rate < 70:
                        self.alert_manager.create_alert(
                            component='network_connectivity',
                            message=f"Network connectivity degraded: {success_rate:.1f}% success rate",
                            severity='critical',
                            details=network_results
                        )
                    elif success_rate < 90:
                        self.alert_manager.create_alert(
                            component='network_connectivity',
                            message=f"Network connectivity issues: {success_rate:.1f}% success rate",
                            severity='high',
                            details=network_results
                        )
                    
                except Exception as e:
                    logger.error(f"Network connectivity check failed: {e}")
                    check_results['network_connectivity'] = {'error': str(e)}
        
        # Database Connection Check
        if (health_config['database_connection']['enabled'] and
            iteration % health_config['database_connection']['interval_multiplier'] == 0):
            
            if 'database' in self.health_checkers:
                try:
                    db_results = self.health_checkers['database'].run_comprehensive_validation()
                    check_results['database_connection'] = db_results
                    
                    success_rate = db_results.get('success_rate', 0)
                    avg_duration = db_results.get('average_connection_time_ms', 0)
                    
                    success_status = self._determine_status(100 - success_rate,  # Invert
                        {'warning': 5, 'critical': 20})  # 95% success = 5% failure
                    duration_status = self._determine_status(avg_duration,
                        health_config['database_connection']['thresholds']['average_duration_ms'])
                    
                    overall_status = 'critical' if 'critical' in [success_status, duration_status] else (
                        'warning' if 'warning' in [success_status, duration_status] else 'healthy'
                    )
                    
                    metric = HealthMetric(
                        timestamp=datetime.now().isoformat(),
                        component='database_connection',
                        metric_name='validation_health',
                        value=success_rate,
                        status=overall_status,
                        threshold_exceeded=overall_status != 'healthy',
                        details=db_results
                    )
                    metrics_collected.append(metric)
                    
                    # Check for alerts
                    if success_rate < 80:
                        self.alert_manager.create_alert(
                            component='database_connection',
                            message=f"Database connection validation failed: {success_rate:.1f}% success rate",
                            severity='critical',
                            details=db_results
                        )
                    elif success_rate < 95:
                        self.alert_manager.create_alert(
                            component='database_connection',
                            message=f"Database connection issues detected: {success_rate:.1f}% success rate",
                            severity='high',
                            details=db_results
                        )
                    
                except Exception as e:
                    logger.error(f"Database connection check failed: {e}")
                    check_results['database_connection'] = {'error': str(e)}
        
        # Database Schema Check
        if (health_config['database_schema']['enabled'] and
            iteration % health_config['database_schema']['interval_multiplier'] == 0):
            
            if 'schema' in self.health_checkers:
                try:
                    schema_results = self.health_checkers['schema'].run_comprehensive_verification()
                    check_results['database_schema'] = schema_results
                    
                    table_info = schema_results.get('table_verification', {})
                    tables_exist = table_info.get('tables_exist', 0)
                    total_tables = table_info.get('total_tables', 0)
                    schema_integrity = (tables_exist / max(total_tables, 1)) * 100
                    
                    schema_status = self._determine_status(100 - schema_integrity,  # Invert
                        {'warning': 5, 'critical': 20})  # 95% integrity = 5% missing
                    
                    metric = HealthMetric(
                        timestamp=datetime.now().isoformat(),
                        component='database_schema',
                        metric_name='schema_integrity',
                        value=schema_integrity,
                        status=schema_status,
                        threshold_exceeded=schema_status != 'healthy',
                        details=schema_results
                    )
                    metrics_collected.append(metric)
                    
                    # Check for alerts
                    if not schema_results.get('overall_success', True):
                        self.alert_manager.create_alert(
                            component='database_schema',
                            message=f"Database schema issues: {schema_integrity:.1f}% integrity",
                            severity='critical' if schema_integrity < 80 else 'high',
                            details=schema_results
                        )
                    
                except Exception as e:
                    logger.error(f"Database schema check failed: {e}")
                    check_results['database_schema'] = {'error': str(e)}
        
        # System Resources Check
        if (health_config['system_resources']['enabled'] and
            iteration % health_config['system_resources']['interval_multiplier'] == 0):
            
            resource_metrics = self.check_system_resources()
            check_results['system_resources'] = {name: asdict(metric) for name, metric in resource_metrics.items()}
            metrics_collected.extend(resource_metrics.values())
            
            # Check for resource alerts
            for metric_name, metric in resource_metrics.items():
                if metric.status == 'critical':
                    self.alert_manager.create_alert(
                        component='system_resources',
                        message=f"Critical {metric_name}: {metric.value:.1f}%",
                        severity='critical',
                        details=metric.details
                    )
                elif metric.status == 'warning':
                    self.alert_manager.create_alert(
                        component='system_resources',
                        message=f"High {metric_name}: {metric.value:.1f}%",
                        severity='medium',
                        details=metric.details
                    )
        
        # Store metrics in history
        for metric in metrics_collected:
            self.metrics_history.append(metric)
            self.trend_analyzer.add_metric(metric)
        
        # Update monitoring stats
        self.monitoring_stats['checks_performed'] += 1
        self.monitoring_stats['alerts_generated'] = len(self.alert_manager.alerts)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'iteration': iteration,
            'checks_performed': len(check_results),
            'metrics_collected': len(metrics_collected),
            'active_alerts': len(self.alert_manager.get_active_alerts()),
            'check_results': check_results
        }
    
    def monitoring_loop(self) -> None:
        """Main monitoring loop"""
        logger.info("Starting continuous health monitoring...")
        iteration = 0
        
        while self.running:
            try:
                start_time = time.time()
                
                # Run health checks
                results = self.run_health_checks(iteration)
                
                # Analyze trends every 10 iterations
                if iteration % 10 == 0:
                    trend_analysis = self.trend_analyzer.analyze_trends()
                    
                    # Create alerts for concerning trends
                    for trend in trend_analysis:
                        if trend['concerning_trend']:
                            self.alert_manager.create_alert(
                                component='trend_analysis',
                                message=f"Concerning trend detected in {trend['metric']}: {trend['trend_direction']}",
                                severity='medium',
                                details=trend
                            )
                
                # Log monitoring summary
                check_duration = time.time() - start_time
                logger.info(f"Health check iteration {iteration} completed in {check_duration:.2f}s - "
                          f"Active alerts: {results['active_alerts']}, Metrics: {results['metrics_collected']}")
                
                iteration += 1
                
                # Sleep until next monitoring interval
                sleep_time = max(0, self.config['monitoring_interval'] - check_duration)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Monitoring iteration failed: {e}")
                logger.error(traceback.format_exc())
                time.sleep(self.config['monitoring_interval'])
        
        logger.info("Continuous health monitoring stopped")
    
    def start_monitoring(self) -> bool:
        """Start continuous monitoring"""
        if self.running:
            logger.warning("Monitoring already running")
            return False
        
        self.running = True
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info(f"Continuous health monitoring started - interval: {self.config['monitoring_interval']}s")
        return True
    
    def stop_monitoring(self) -> bool:
        """Stop continuous monitoring"""
        if not self.running:
            return False
        
        self.running = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10)
            
            if self.monitoring_thread.is_alive():
                logger.warning("Monitoring thread did not stop gracefully")
                return False
        
        logger.info("Continuous health monitoring stopped")
        return True
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status and statistics"""
        active_alerts = self.alert_manager.get_active_alerts()
        
        # Get recent metrics (last 10)
        recent_metrics = list(self.metrics_history)[-10:] if self.metrics_history else []
        
        # Calculate uptime
        uptime_start = datetime.fromisoformat(self.monitoring_stats['uptime_start'])
        uptime_seconds = (datetime.now() - uptime_start).total_seconds()
        
        return {
            'monitoring_active': self.running,
            'uptime_seconds': round(uptime_seconds, 1),
            'uptime_formatted': str(timedelta(seconds=int(uptime_seconds))),
            'monitoring_interval': self.config['monitoring_interval'],
            'statistics': self.monitoring_stats,
            'active_alerts': {
                'count': len(active_alerts),
                'by_severity': {
                    severity: len([a for a in active_alerts if a.severity == severity])
                    for severity in ['low', 'medium', 'high', 'critical']
                },
                'alerts': [asdict(alert) for alert in active_alerts[-5:]]  # Last 5 alerts
            },
            'recent_metrics': [asdict(metric) for metric in recent_metrics],
            'health_checkers_available': list(self.health_checkers.keys()),
            'trend_analysis_metrics': len(self.trend_analyzer.metric_history)
        }
    
    def save_monitoring_report(self, filename: str = None) -> str:
        """Save comprehensive monitoring report"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/home/user/Testing/ai-model-validation-platform/backend/logs/health_monitoring_report_{timestamp}.json'
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Generate comprehensive report
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'monitoring_status': self.get_monitoring_status(),
            'trend_analysis': self.trend_analyzer.analyze_trends(),
            'all_alerts': [asdict(alert) for alert in self.alert_manager.alerts],
            'metrics_summary': {
                'total_metrics': len(self.metrics_history),
                'metrics_by_component': {},
                'health_distribution': {'healthy': 0, 'warning': 0, 'critical': 0}
            },
            'configuration': self.config
        }
        
        # Calculate metrics summary
        for metric in self.metrics_history:
            component = metric.component
            if component not in report['metrics_summary']['metrics_by_component']:
                report['metrics_summary']['metrics_by_component'][component] = 0
            report['metrics_summary']['metrics_by_component'][component] += 1
            
            if metric.status in report['metrics_summary']['health_distribution']:
                report['metrics_summary']['health_distribution'][metric.status] += 1
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return filename

def main():
    """Main continuous monitoring execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Continuous Health Monitoring Daemon')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--interval', type=int, help='Monitoring interval in seconds')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--status', action='store_true', help='Show monitoring status')
    parser.add_argument('--stop', action='store_true', help='Stop running monitor')
    parser.add_argument('--report', help='Generate monitoring report to file')
    
    args = parser.parse_args()
    
    # Load custom configuration if provided
    config = None
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {args.config}")
        except Exception as e:
            logger.error(f"Could not load configuration: {e}")
    
    # Override interval if specified
    if args.interval and config:
        config['monitoring_interval'] = args.interval
    elif args.interval:
        config = {'monitoring_interval': args.interval}
    
    # Create monitor instance
    monitor = ContinuousHealthMonitor(config)
    
    if args.status:
        # Show status
        status = monitor.get_monitoring_status()
        print(f"\n=== Health Monitoring Status ===")
        print(f"Active: {'✅' if status['monitoring_active'] else '❌'}")
        print(f"Uptime: {status['uptime_formatted']}")
        print(f"Interval: {status['monitoring_interval']}s")
        print(f"Checks Performed: {status['statistics']['checks_performed']}")
        print(f"Active Alerts: {status['active_alerts']['count']}")
        
        if status['active_alerts']['count'] > 0:
            print(f"\nAlert Summary:")
            for severity, count in status['active_alerts']['by_severity'].items():
                if count > 0:
                    print(f"  {severity.title()}: {count}")
        
        print(f"\nAvailable Checkers: {', '.join(status['health_checkers_available'])}")
    
    elif args.report:
        # Generate report
        print("Generating monitoring report...")
        report_file = monitor.save_monitoring_report(args.report)
        print(f"Report saved to: {report_file}")
    
    elif args.daemon:
        # Run as daemon
        try:
            if monitor.start_monitoring():
                print(f"Health monitoring daemon started (PID: {os.getpid()})")
                print(f"Monitoring interval: {monitor.config['monitoring_interval']}s")
                print(f"Logs: /home/user/Testing/ai-model-validation-platform/backend/logs/health_monitor.log")
                print("Press Ctrl+C to stop...")
                
                # Keep main thread alive
                while monitor.running:
                    time.sleep(1)
            else:
                print("Failed to start monitoring daemon")
        except KeyboardInterrupt:
            print("\nShutting down monitoring daemon...")
            monitor.stop_monitoring()
        except Exception as e:
            logger.error(f"Daemon failed: {e}")
            monitor.stop_monitoring()
    
    else:
        # Run single check cycle
        print("Running single health check cycle...")
        results = monitor.run_health_checks(0)
        
        print(f"\n=== Health Check Results ===")
        print(f"Checks Performed: {results['checks_performed']}")
        print(f"Metrics Collected: {results['metrics_collected']}")
        print(f"Active Alerts: {results['active_alerts']}")
        
        if results['active_alerts'] > 0:
            active_alerts = monitor.alert_manager.get_active_alerts()
            print(f"\nRecent Alerts:")
            for alert in active_alerts[-3:]:  # Show last 3 alerts
                print(f"  {alert.severity.upper()}: {alert.component} - {alert.message}")
        
        # Show component status
        for component, result in results['check_results'].items():
            if isinstance(result, dict) and 'error' not in result:
                print(f"\n{component}: ✅ OK")
            elif isinstance(result, dict) and 'error' in result:
                print(f"\n{component}: ❌ ERROR - {result['error']}")
            else:
                print(f"\n{component}: ❓ Unknown status")

if __name__ == '__main__':
    main()
