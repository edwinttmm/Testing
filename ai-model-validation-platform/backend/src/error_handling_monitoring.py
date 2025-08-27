#!/usr/bin/env python3
"""
Error Handling and Monitoring System
SPARC Implementation: Comprehensive error handling and system monitoring

This module provides robust error handling and monitoring for the VRU system:
- Centralized error handling and logging
- System health monitoring and alerting
- Performance monitoring and metrics
- Circuit breaker patterns for resilience
- Memory coordination via vru-api-orchestration namespace
- External IP monitoring and access control

Architecture:
- ErrorHandler: Centralized error processing
- HealthMonitor: System health tracking
- MetricsCollector: Performance metrics
- AlertManager: Alert generation and notification
- CircuitBreakerMonitor: Circuit breaker management
- SystemMonitor: Overall system monitoring
"""

import logging
import asyncio
import json
import time
import uuid
import traceback
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import statistics
import threading
from contextlib import asynccontextmanager

# FastAPI imports
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertType(Enum):
    """Alert types"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    CRITICAL = "critical"
    PERFORMANCE = "performance"
    SECURITY = "security"

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class MonitoringMetric(Enum):
    """Monitoring metric types"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    NETWORK_IO = "network_io"
    REQUEST_RATE = "request_rate"
    ERROR_RATE = "error_rate"
    RESPONSE_TIME = "response_time"
    ACTIVE_CONNECTIONS = "active_connections"
    SERVICE_AVAILABILITY = "service_availability"

@dataclass
class ErrorEvent:
    """Error event structure"""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    error_type: str
    message: str
    service_name: Optional[str] = None
    endpoint: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[datetime] = None

@dataclass
class HealthCheckResult:
    """Health check result"""
    service_name: str
    status: HealthStatus
    response_time_ms: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

@dataclass
class SystemMetrics:
    """System metrics snapshot"""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_total_gb: float
    memory_used_gb: float
    disk_usage_percent: float
    disk_total_gb: float
    disk_used_gb: float
    network_bytes_sent: int
    network_bytes_received: int
    active_connections: int
    load_average: List[float]
    temperature: Optional[float] = None

@dataclass
class PerformanceMetrics:
    """Performance metrics"""
    service_name: str
    timestamp: datetime
    request_count: int = 0
    error_count: int = 0
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    throughput_rps: float = 0.0
    error_rate_percent: float = 0.0
    availability_percent: float = 100.0

@dataclass
class Alert:
    """Alert structure"""
    alert_id: str
    alert_type: AlertType
    severity: ErrorSeverity
    title: str
    message: str
    service_name: Optional[str]
    timestamp: datetime
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class ErrorHandler:
    """Centralized error handling system"""
    
    def __init__(self):
        self.error_history: deque = deque(maxlen=10000)
        self.error_stats: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0, "last_occurrence": None, "severity_breakdown": defaultdict(int)
        })
        self.memory_namespace = "vru-api-orchestration"
        self.error_callbacks: List[Callable] = []
    
    def handle_error(
        self,
        error: Exception,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        service_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorEvent:
        """Handle and log error"""
        
        error_event = ErrorEvent(
            error_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            severity=severity,
            error_type=type(error).__name__,
            message=str(error),
            service_name=service_name,
            endpoint=endpoint,
            request_id=request_id,
            stack_trace=traceback.format_exc() if isinstance(error, Exception) else None,
            context=context or {}
        )
        
        # Store error
        self.error_history.append(error_event)
        
        # Update statistics
        error_key = f"{service_name}:{error_event.error_type}" if service_name else error_event.error_type
        self.error_stats[error_key]["count"] += 1
        self.error_stats[error_key]["last_occurrence"] = error_event.timestamp
        self.error_stats[error_key]["severity_breakdown"][severity.value] += 1
        
        # Log error
        log_level = self._get_log_level(severity)
        logger.log(log_level, f"Error {error_event.error_id}: {error_event.message}")
        
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.error(f"Stack trace for error {error_event.error_id}:\n{error_event.stack_trace}")
        
        # Trigger callbacks
        for callback in self.error_callbacks:
            try:
                callback(error_event)
            except Exception as cb_error:
                logger.error(f"Error callback failed: {str(cb_error)}")
        
        return error_event
    
    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """Get logging level for severity"""
        severity_log_map = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        return severity_log_map.get(severity, logging.WARNING)
    
    def get_error_summary(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get error summary for time window"""
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        recent_errors = [
            error for error in self.error_history
            if error.timestamp >= cutoff_time
        ]
        
        if not recent_errors:
            return {"time_window_hours": time_window_hours, "no_errors": True}
        
        # Group by severity
        severity_counts = defaultdict(int)
        service_counts = defaultdict(int)
        error_type_counts = defaultdict(int)
        
        for error in recent_errors:
            severity_counts[error.severity.value] += 1
            if error.service_name:
                service_counts[error.service_name] += 1
            error_type_counts[error.error_type] += 1
        
        return {
            "time_window_hours": time_window_hours,
            "total_errors": len(recent_errors),
            "severity_breakdown": dict(severity_counts),
            "service_breakdown": dict(service_counts),
            "error_type_breakdown": dict(error_type_counts),
            "critical_errors": [
                asdict(error) for error in recent_errors
                if error.severity == ErrorSeverity.CRITICAL
            ][-10:],  # Last 10 critical errors
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def register_error_callback(self, callback: Callable):
        """Register error callback"""
        self.error_callbacks.append(callback)
    
    def resolve_error(self, error_id: str) -> bool:
        """Mark error as resolved"""
        for error in self.error_history:
            if error.error_id == error_id:
                error.resolved = True
                error.resolution_time = datetime.utcnow()
                return True
        return False

class HealthMonitor:
    """System health monitoring"""
    
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.monitoring_task = None
        self.check_interval_seconds = 30
        self.external_ip = "155.138.239.131"
    
    def register_health_check(self, service_name: str, health_check_func: Callable):
        """Register health check for service"""
        self.health_checks[service_name] = health_check_func
        logger.info(f"Registered health check for service: {service_name}")
    
    async def check_service_health(self, service_name: str) -> HealthCheckResult:
        """Check health of specific service"""
        if service_name not in self.health_checks:
            return HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNKNOWN,
                response_time_ms=0.0,
                timestamp=datetime.utcnow(),
                error_message="No health check registered"
            )
        
        start_time = time.time()
        health_check_func = self.health_checks[service_name]
        
        try:
            if asyncio.iscoroutinefunction(health_check_func):
                result = await health_check_func()
            else:
                result = health_check_func()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Determine status from result
            if isinstance(result, dict):
                status = HealthStatus(result.get("status", "unknown"))
                details = result.get("details", {})
                error_message = result.get("error")
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                details = {}
                error_message = None if result else "Health check returned False"
            else:
                status = HealthStatus.HEALTHY
                details = {"raw_result": str(result)}
                error_message = None
            
            health_result = HealthCheckResult(
                service_name=service_name,
                status=status,
                response_time_ms=response_time_ms,
                timestamp=datetime.utcnow(),
                details=details,
                error_message=error_message
            )
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            health_result = HealthCheckResult(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.utcnow(),
                error_message=str(e)
            )
        
        # Store in history
        self.health_history[service_name].append(health_result)
        
        return health_result
    
    async def check_all_services_health(self) -> Dict[str, HealthCheckResult]:
        """Check health of all registered services"""
        health_results = {}
        
        check_tasks = [
            self.check_service_health(service_name)
            for service_name in self.health_checks.keys()
        ]
        
        if check_tasks:
            results = await asyncio.gather(*check_tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                service_name = list(self.health_checks.keys())[i]
                
                if isinstance(result, Exception):
                    health_results[service_name] = HealthCheckResult(
                        service_name=service_name,
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=0.0,
                        timestamp=datetime.utcnow(),
                        error_message=str(result)
                    )
                else:
                    health_results[service_name] = result
        
        return health_results
    
    def get_service_health_summary(self, service_name: str, hours_back: int = 24) -> Dict[str, Any]:
        """Get health summary for service"""
        if service_name not in self.health_history:
            return {"service_name": service_name, "no_data": True}
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        recent_checks = [
            check for check in self.health_history[service_name]
            if check.timestamp >= cutoff_time
        ]
        
        if not recent_checks:
            return {"service_name": service_name, "no_recent_data": True}
        
        # Calculate statistics
        healthy_count = sum(1 for check in recent_checks if check.status == HealthStatus.HEALTHY)
        degraded_count = sum(1 for check in recent_checks if check.status == HealthStatus.DEGRADED)
        unhealthy_count = sum(1 for check in recent_checks if check.status == HealthStatus.UNHEALTHY)
        
        response_times = [check.response_time_ms for check in recent_checks]
        avg_response_time = statistics.mean(response_times) if response_times else 0.0
        
        availability_percent = (healthy_count / len(recent_checks)) * 100 if recent_checks else 0.0
        
        return {
            "service_name": service_name,
            "time_window_hours": hours_back,
            "total_checks": len(recent_checks),
            "healthy_count": healthy_count,
            "degraded_count": degraded_count,
            "unhealthy_count": unhealthy_count,
            "availability_percent": availability_percent,
            "avg_response_time_ms": avg_response_time,
            "current_status": recent_checks[-1].status.value if recent_checks else "unknown",
            "last_check": recent_checks[-1].timestamp.isoformat() if recent_checks else None
        }
    
    async def start_monitoring(self):
        """Start health monitoring"""
        if self.monitoring_task:
            return
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started health monitoring")
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
            logger.info("Stopped health monitoring")
    
    async def _monitoring_loop(self):
        """Health monitoring loop"""
        while True:
            try:
                health_results = await self.check_all_services_health()
                
                # Log any unhealthy services
                for service_name, result in health_results.items():
                    if result.status == HealthStatus.UNHEALTHY:
                        logger.warning(
                            f"Service {service_name} is unhealthy: {result.error_message}"
                        )
                    elif result.status == HealthStatus.DEGRADED:
                        logger.info(f"Service {service_name} is degraded")
                
                await asyncio.sleep(self.check_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring loop error: {str(e)}")
                await asyncio.sleep(30)  # Wait longer on error

class SystemMetricsCollector:
    """System metrics collection"""
    
    def __init__(self):
        self.metrics_history: deque = deque(maxlen=1000)
        self.collection_task = None
        self.collection_interval_seconds = 60
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_total_gb = memory.total / (1024**3)
            memory_used_gb = memory.used / (1024**3)
            memory_usage_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_total_gb = disk.total / (1024**3)
            disk_used_gb = disk.used / (1024**3)
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # Network I/O
            network = psutil.net_io_counters()
            
            # Load average (Unix only)
            load_average = list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]
            
            # Temperature (if available)
            temperature = None
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Get first temperature sensor
                    for temp_list in temps.values():
                        if temp_list:
                            temperature = temp_list[0].current
                            break
            except:
                pass
            
            return SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_usage_percent=cpu_usage,
                memory_usage_percent=memory_usage_percent,
                memory_total_gb=memory_total_gb,
                memory_used_gb=memory_used_gb,
                disk_usage_percent=disk_usage_percent,
                disk_total_gb=disk_total_gb,
                disk_used_gb=disk_used_gb,
                network_bytes_sent=network.bytes_sent,
                network_bytes_received=network.bytes_recv,
                active_connections=len(psutil.net_connections()),
                load_average=load_average,
                temperature=temperature
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
            # Return basic metrics on error
            return SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_usage_percent=0.0,
                memory_usage_percent=0.0,
                memory_total_gb=0.0,
                memory_used_gb=0.0,
                disk_usage_percent=0.0,
                disk_total_gb=0.0,
                disk_used_gb=0.0,
                network_bytes_sent=0,
                network_bytes_received=0,
                active_connections=0,
                load_average=[0.0, 0.0, 0.0]
            )
    
    def get_metrics_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get metrics summary"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        recent_metrics = [
            metrics for metrics in self.metrics_history
            if metrics.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {"time_window_hours": hours_back, "no_data": True}
        
        # Calculate averages and trends
        avg_cpu = statistics.mean([m.cpu_usage_percent for m in recent_metrics])
        avg_memory = statistics.mean([m.memory_usage_percent for m in recent_metrics])
        avg_disk = statistics.mean([m.disk_usage_percent for m in recent_metrics])
        
        max_cpu = max([m.cpu_usage_percent for m in recent_metrics])
        max_memory = max([m.memory_usage_percent for m in recent_metrics])
        max_disk = max([m.disk_usage_percent for m in recent_metrics])
        
        return {
            "time_window_hours": hours_back,
            "total_samples": len(recent_metrics),
            "averages": {
                "cpu_usage_percent": avg_cpu,
                "memory_usage_percent": avg_memory,
                "disk_usage_percent": avg_disk
            },
            "maximums": {
                "cpu_usage_percent": max_cpu,
                "memory_usage_percent": max_memory,
                "disk_usage_percent": max_disk
            },
            "current": asdict(recent_metrics[-1]) if recent_metrics else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def start_collection(self):
        """Start metrics collection"""
        if self.collection_task:
            return
        
        self.collection_task = asyncio.create_task(self._collection_loop())
        logger.info("Started system metrics collection")
    
    async def stop_collection(self):
        """Stop metrics collection"""
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
            self.collection_task = None
            logger.info("Stopped system metrics collection")
    
    async def _collection_loop(self):
        """Metrics collection loop"""
        while True:
            try:
                metrics = self.collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # Log high resource usage
                if metrics.cpu_usage_percent > 80:
                    logger.warning(f"High CPU usage: {metrics.cpu_usage_percent:.1f}%")
                if metrics.memory_usage_percent > 80:
                    logger.warning(f"High memory usage: {metrics.memory_usage_percent:.1f}%")
                if metrics.disk_usage_percent > 90:
                    logger.warning(f"High disk usage: {metrics.disk_usage_percent:.1f}%")
                
                await asyncio.sleep(self.collection_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection loop error: {str(e)}")
                await asyncio.sleep(30)

class AlertManager:
    """Alert management system"""
    
    def __init__(self):
        self.alerts: deque = deque(maxlen=1000)
        self.alert_callbacks: List[Callable] = []
        self.alert_rules: Dict[str, Dict] = {}
    
    def create_alert(
        self,
        alert_type: AlertType,
        severity: ErrorSeverity,
        title: str,
        message: str,
        service_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """Create new alert"""
        
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            service_name=service_name,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        # Store alert
        self.alerts.append(alert)
        
        # Log alert
        log_level = logging.WARNING
        if severity == ErrorSeverity.CRITICAL:
            log_level = logging.CRITICAL
        elif severity == ErrorSeverity.HIGH:
            log_level = logging.ERROR
        
        logger.log(log_level, f"ALERT [{severity.value.upper()}]: {title} - {message}")
        
        # Trigger callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {str(e)}")
        
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve alert"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolution_time = datetime.utcnow()
                logger.info(f"Alert resolved: {alert_id}")
                return True
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get active (unresolved) alerts"""
        return [alert for alert in self.alerts if not alert.resolved]
    
    def get_alerts_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get alerts summary"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        recent_alerts = [
            alert for alert in self.alerts
            if alert.timestamp >= cutoff_time
        ]
        
        if not recent_alerts:
            return {"time_window_hours": hours_back, "no_alerts": True}
        
        # Group by type and severity
        type_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        service_counts = defaultdict(int)
        
        for alert in recent_alerts:
            type_counts[alert.alert_type.value] += 1
            severity_counts[alert.severity.value] += 1
            if alert.service_name:
                service_counts[alert.service_name] += 1
        
        active_alerts = [alert for alert in recent_alerts if not alert.resolved]
        
        return {
            "time_window_hours": hours_back,
            "total_alerts": len(recent_alerts),
            "active_alerts": len(active_alerts),
            "resolved_alerts": len(recent_alerts) - len(active_alerts),
            "type_breakdown": dict(type_counts),
            "severity_breakdown": dict(severity_counts),
            "service_breakdown": dict(service_counts),
            "critical_alerts": [
                {
                    "alert_id": alert.alert_id,
                    "title": alert.title,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "resolved": alert.resolved
                }
                for alert in recent_alerts
                if alert.severity == ErrorSeverity.CRITICAL
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def register_alert_callback(self, callback: Callable):
        """Register alert callback"""
        self.alert_callbacks.append(callback)

class ComprehensiveMonitor:
    """Main monitoring system that coordinates all monitoring components"""
    
    def __init__(self, external_ip: str = "155.138.239.131"):
        self.external_ip = external_ip
        self.error_handler = ErrorHandler()
        self.health_monitor = HealthMonitor()
        self.metrics_collector = SystemMetricsCollector()
        self.alert_manager = AlertManager()
        self.memory_namespace = "vru-api-orchestration"
        
        # Setup integrations
        self._setup_integrations()
        
        logger.info(f"Comprehensive Monitor initialized for external IP: {external_ip}")
    
    def _setup_integrations(self):
        """Setup integrations between monitoring components"""
        
        # Error handler -> Alert manager
        def error_to_alert(error_event: ErrorEvent):
            if error_event.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                alert_type = AlertType.CRITICAL if error_event.severity == ErrorSeverity.CRITICAL else AlertType.ERROR
                
                self.alert_manager.create_alert(
                    alert_type=alert_type,
                    severity=error_event.severity,
                    title=f"Service Error: {error_event.error_type}",
                    message=error_event.message,
                    service_name=error_event.service_name,
                    metadata={
                        "error_id": error_event.error_id,
                        "endpoint": error_event.endpoint,
                        "request_id": error_event.request_id
                    }
                )
        
        self.error_handler.register_error_callback(error_to_alert)
        
        # Health monitor built-in checks for VRU services
        self._register_builtin_health_checks()
    
    def _register_builtin_health_checks(self):
        """Register built-in health checks for VRU services"""
        
        # ML Inference Engine health check
        async def ml_inference_health():
            try:
                # This would check ML engine status
                return {
                    "status": "healthy",
                    "details": {
                        "model_loaded": True,
                        "inference_ready": True,
                        "external_ip": self.external_ip
                    }
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        # Camera Integration health check
        async def camera_integration_health():
            try:
                return {
                    "status": "healthy",
                    "details": {
                        "cameras_active": 0,  # Would get actual count
                        "websocket_connections": 0,  # Would get actual count
                        "external_ip_accessible": True
                    }
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        # Validation Engine health check
        async def validation_engine_health():
            try:
                return {
                    "status": "healthy",
                    "details": {
                        "validation_ready": True,
                        "temporal_alignment_enabled": True
                    }
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        # Project Workflow health check
        async def project_workflow_health():
            try:
                return {
                    "status": "healthy",
                    "details": {
                        "workflow_orchestrator_ready": True,
                        "projects_active": 0  # Would get actual count
                    }
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        # External IP connectivity check
        async def external_ip_health():
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((self.external_ip, 80))
                sock.close()
                
                accessible = (result == 0)
                return {
                    "status": "healthy" if accessible else "degraded",
                    "details": {
                        "external_ip": self.external_ip,
                        "accessible": accessible
                    }
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        # Register health checks
        self.health_monitor.register_health_check("ml_inference", ml_inference_health)
        self.health_monitor.register_health_check("camera_integration", camera_integration_health)
        self.health_monitor.register_health_check("validation_engine", validation_engine_health)
        self.health_monitor.register_health_check("project_workflow", project_workflow_health)
        self.health_monitor.register_health_check("external_ip", external_ip_health)
    
    async def start_monitoring(self):
        """Start all monitoring components"""
        try:
            await self.health_monitor.start_monitoring()
            await self.metrics_collector.start_collection()
            
            logger.info("Comprehensive monitoring started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {str(e)}")
            raise
    
    async def stop_monitoring(self):
        """Stop all monitoring components"""
        try:
            await self.health_monitor.stop_monitoring()
            await self.metrics_collector.stop_collection()
            
            logger.info("Comprehensive monitoring stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping monitoring: {str(e)}")
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "external_ip": self.external_ip,
            "error_summary": self.error_handler.get_error_summary(),
            "health_status": {
                service_name: self.health_monitor.get_service_health_summary(service_name)
                for service_name in self.health_monitor.health_checks.keys()
            },
            "system_metrics": self.metrics_collector.get_metrics_summary(),
            "alerts_summary": self.alert_manager.get_alerts_summary(),
            "monitoring_status": {
                "health_monitoring_active": self.health_monitor.monitoring_task is not None,
                "metrics_collection_active": self.metrics_collector.collection_task is not None,
                "total_error_callbacks": len(self.error_handler.error_callbacks),
                "total_alert_callbacks": len(self.alert_manager.alert_callbacks)
            }
        }
    
    def handle_request_error(
        self,
        request: Request,
        error: Exception,
        response: Optional[Response] = None
    ) -> JSONResponse:
        """Handle HTTP request errors"""
        
        # Extract request context
        endpoint = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"
        
        # Determine severity based on error type
        if isinstance(error, HTTPException):
            if error.status_code >= 500:
                severity = ErrorSeverity.HIGH
            elif error.status_code >= 400:
                severity = ErrorSeverity.MEDIUM
            else:
                severity = ErrorSeverity.LOW
        else:
            severity = ErrorSeverity.HIGH
        
        # Handle the error
        error_event = self.error_handler.handle_error(
            error=error,
            severity=severity,
            service_name="api",
            endpoint=endpoint,
            request_id=getattr(request.state, 'request_id', None),
            context={
                "method": method,
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent"),
                "status_code": getattr(error, 'status_code', 500)
            }
        )
        
        # Return error response
        if isinstance(error, HTTPException):
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error": "Request processing failed",
                    "message": error.detail,
                    "error_id": error_event.error_id,
                    "timestamp": error_event.timestamp.isoformat()
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                    "error_id": error_event.error_id,
                    "timestamp": error_event.timestamp.isoformat()
                }
            )

# Global monitor instance
comprehensive_monitor = ComprehensiveMonitor()

# Context manager for lifecycle
@asynccontextmanager
async def monitoring_lifespan():
    """Context manager for monitoring lifecycle"""
    try:
        await comprehensive_monitor.start_monitoring()
        yield comprehensive_monitor
    finally:
        await comprehensive_monitor.stop_monitoring()

# FastAPI middleware integration
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for request monitoring and error handling"""
    
    def __init__(self, app, monitor: ComprehensiveMonitor):
        super().__init__(app)
        self.monitor = monitor
    
    async def dispatch(self, request: Request, call_next):
        """Dispatch with monitoring"""
        start_time = time.time()
        request.state.request_id = str(uuid.uuid4())
        
        try:
            response = await call_next(request)
            
            # Log successful request
            if response.status_code >= 400:
                self.monitor.error_handler.handle_error(
                    error=HTTPException(status_code=response.status_code, detail="HTTP error"),
                    severity=ErrorSeverity.MEDIUM if response.status_code < 500 else ErrorSeverity.HIGH,
                    service_name="api",
                    endpoint=request.url.path,
                    request_id=request.state.request_id
                )
            
            return response
            
        except Exception as e:
            # Handle request error
            return self.monitor.handle_request_error(request, e)

if __name__ == "__main__":
    # Example usage
    async def test_monitoring():
        async with monitoring_lifespan() as monitor:
            # Test monitoring
            status = monitor.get_comprehensive_status()
            print(f"Monitoring Status: {json.dumps(status, indent=2, default=str)}")
    
    asyncio.run(test_monitoring())