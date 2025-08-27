#!/usr/bin/env python3
"""
Service Coordination Middleware
SPARC Implementation: Middleware for coordinating VRU services

This module provides middleware for coordinating all VRU services:
- Service discovery and registration
- Load balancing and request routing
- Circuit breaker pattern for resilience
- Performance monitoring and metrics
- Memory coordination via vru-api-orchestration namespace
- Error handling and recovery

Architecture:
- ServiceRegistry: Manages service discovery
- LoadBalancer: Distributes requests across services
- CircuitBreaker: Provides fault tolerance
- MetricsCollector: Tracks performance metrics
- MemoryCoordinator: Manages shared state
"""

import logging
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import statistics
import threading

# FastAPI middleware imports
from fastapi import Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

class ServiceState(Enum):
    """Service state enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class CircuitState(Enum):
    """Circuit breaker state enumeration"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class LoadBalancingStrategy(Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    HEALTH_BASED = "health_based"

@dataclass
class ServiceInstance:
    """Service instance registration"""
    service_id: str
    service_name: str
    host: str
    port: int
    health_endpoint: str = "/health"
    weight: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None
    state: ServiceState = ServiceState.UNKNOWN
    response_time_ms: float = 0.0
    error_count: int = 0
    request_count: int = 0

@dataclass
class RequestMetrics:
    """Request metrics tracking"""
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    service_name: str
    timestamp: datetime
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    request_size_bytes: int = 0
    response_size_bytes: int = 0

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    request_timeout_seconds: int = 30
    monitoring_period_seconds: int = 300

@dataclass
class ServiceMetrics:
    """Service performance metrics"""
    service_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    error_rate: float = 0.0
    current_connections: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

class ServiceRegistry:
    """Service discovery and registration system"""
    
    def __init__(self):
        self.services: Dict[str, List[ServiceInstance]] = defaultdict(list)
        self.service_metrics: Dict[str, ServiceMetrics] = {}
        self.lock = threading.RLock()
        self.health_check_interval = 30  # seconds
        self.health_check_task = None
    
    def register_service(self, instance: ServiceInstance) -> bool:
        """Register a service instance"""
        try:
            with self.lock:
                # Check if service already exists
                existing_services = self.services[instance.service_name]
                for i, existing in enumerate(existing_services):
                    if existing.service_id == instance.service_id:
                        # Update existing service
                        existing_services[i] = instance
                        logger.info(f"Updated service instance: {instance.service_id}")
                        return True
                
                # Add new service instance
                self.services[instance.service_name].append(instance)
                
                # Initialize metrics
                if instance.service_name not in self.service_metrics:
                    self.service_metrics[instance.service_name] = ServiceMetrics(
                        service_name=instance.service_name
                    )
                
                logger.info(f"Registered new service instance: {instance.service_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to register service {instance.service_id}: {str(e)}")
            return False
    
    def deregister_service(self, service_id: str) -> bool:
        """Deregister a service instance"""
        try:
            with self.lock:
                for service_name, instances in self.services.items():
                    for i, instance in enumerate(instances):
                        if instance.service_id == service_id:
                            instances.pop(i)
                            logger.info(f"Deregistered service instance: {service_id}")
                            return True
                
                logger.warning(f"Service instance not found for deregistration: {service_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to deregister service {service_id}: {str(e)}")
            return False
    
    def get_healthy_instances(self, service_name: str) -> List[ServiceInstance]:
        """Get healthy instances of a service"""
        with self.lock:
            instances = self.services.get(service_name, [])
            return [inst for inst in instances if inst.state == ServiceState.HEALTHY]
    
    def get_all_instances(self, service_name: str) -> List[ServiceInstance]:
        """Get all instances of a service"""
        with self.lock:
            return self.services.get(service_name, []).copy()
    
    def update_instance_health(self, service_id: str, state: ServiceState, 
                              response_time_ms: float = 0.0, error_count: int = 0):
        """Update health status of service instance"""
        with self.lock:
            for instances in self.services.values():
                for instance in instances:
                    if instance.service_id == service_id:
                        instance.state = state
                        instance.response_time_ms = response_time_ms
                        instance.error_count = error_count
                        instance.last_health_check = datetime.utcnow()
                        return True
        return False
    
    async def start_health_monitoring(self):
        """Start health check monitoring"""
        if self.health_check_task:
            return
        
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Started service health monitoring")
    
    async def stop_health_monitoring(self):
        """Stop health check monitoring"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
            self.health_check_task = None
            logger.info("Stopped service health monitoring")
    
    async def _health_check_loop(self):
        """Health check monitoring loop"""
        import aiohttp
        
        while True:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    with self.lock:
                        all_instances = [
                            instance for instances in self.services.values() 
                            for instance in instances
                        ]
                    
                    # Check health for all instances
                    health_check_tasks = [
                        self._check_instance_health(session, instance)
                        for instance in all_instances
                    ]
                    
                    if health_check_tasks:
                        await asyncio.gather(*health_check_tasks, return_exceptions=True)
                
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {str(e)}")
                await asyncio.sleep(5)
    
    async def _check_instance_health(self, session, instance: ServiceInstance):
        """Check health of single service instance"""
        health_url = f"http://{instance.host}:{instance.port}{instance.health_endpoint}"
        
        try:
            start_time = time.time()
            
            async with session.get(health_url) as response:
                response_time = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    self.update_instance_health(
                        instance.service_id, 
                        ServiceState.HEALTHY, 
                        response_time
                    )
                else:
                    self.update_instance_health(
                        instance.service_id, 
                        ServiceState.DEGRADED, 
                        response_time
                    )
                    
        except Exception as e:
            logger.warning(f"Health check failed for {instance.service_id}: {str(e)}")
            self.update_instance_health(
                instance.service_id, 
                ServiceState.UNHEALTHY, 
                error_count=instance.error_count + 1
            )
    
    def get_service_metrics(self, service_name: str) -> Optional[ServiceMetrics]:
        """Get metrics for a service"""
        return self.service_metrics.get(service_name)
    
    def update_service_metrics(self, service_name: str, metrics_update: Dict[str, Any]):
        """Update service metrics"""
        if service_name not in self.service_metrics:
            self.service_metrics[service_name] = ServiceMetrics(service_name=service_name)
        
        metrics = self.service_metrics[service_name]
        
        for key, value in metrics_update.items():
            if hasattr(metrics, key):
                setattr(metrics, key, value)
        
        metrics.last_updated = datetime.utcnow()

class LoadBalancer:
    """Load balancing for service requests"""
    
    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.HEALTH_BASED):
        self.strategy = strategy
        self.round_robin_counters = defaultdict(int)
        self.connection_counts = defaultdict(int)
    
    def select_instance(self, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        """Select service instance based on load balancing strategy"""
        if not instances:
            return None
        
        if len(instances) == 1:
            return instances[0]
        
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_select(instances)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select(instances)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections_select(instances)
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return self._random_select(instances)
        elif self.strategy == LoadBalancingStrategy.HEALTH_BASED:
            return self._health_based_select(instances)
        else:
            return instances[0]
    
    def _round_robin_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Round robin selection"""
        service_name = instances[0].service_name
        counter = self.round_robin_counters[service_name]
        selected = instances[counter % len(instances)]
        self.round_robin_counters[service_name] = counter + 1
        return selected
    
    def _weighted_round_robin_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Weighted round robin selection"""
        total_weight = sum(inst.weight for inst in instances)
        if total_weight == 0:
            return self._round_robin_select(instances)
        
        import random
        weight_point = random.uniform(0, total_weight)
        current_weight = 0
        
        for instance in instances:
            current_weight += instance.weight
            if current_weight >= weight_point:
                return instance
        
        return instances[-1]
    
    def _least_connections_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Least connections selection"""
        min_connections = min(
            self.connection_counts[inst.service_id] for inst in instances
        )
        
        candidates = [
            inst for inst in instances
            if self.connection_counts[inst.service_id] == min_connections
        ]
        
        if len(candidates) == 1:
            return candidates[0]
        else:
            return self._health_based_select(candidates)
    
    def _random_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Random selection"""
        import random
        return random.choice(instances)
    
    def _health_based_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Health-based selection (prefer fastest response time)"""
        healthy_instances = [inst for inst in instances if inst.state == ServiceState.HEALTHY]
        
        if not healthy_instances:
            # Fallback to degraded instances
            healthy_instances = [inst for inst in instances if inst.state == ServiceState.DEGRADED]
        
        if not healthy_instances:
            # Last resort: any instance
            healthy_instances = instances
        
        # Select instance with best response time
        return min(healthy_instances, key=lambda x: x.response_time_ms or float('inf'))
    
    def increment_connection(self, service_id: str):
        """Increment connection count for service"""
        self.connection_counts[service_id] += 1
    
    def decrement_connection(self, service_id: str):
        """Decrement connection count for service"""
        if self.connection_counts[service_id] > 0:
            self.connection_counts[service_id] -= 1

class CircuitBreaker:
    """Circuit breaker for fault tolerance"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.next_attempt_time = None
        self.success_count = 0
        self.lock = threading.Lock()
    
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        with self.lock:
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                if datetime.utcnow() >= self.next_attempt_time:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    return True
                return False
            else:  # HALF_OPEN
                return True
    
    def record_success(self):
        """Record successful request"""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= 3:  # Require 3 successes to close
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.last_failure_time = None
                    self.next_attempt_time = None
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0
    
    def record_failure(self):
        """Record failed request"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.next_attempt_time = (
                        datetime.utcnow() + 
                        timedelta(seconds=self.config.recovery_timeout_seconds)
                    )
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.next_attempt_time = (
                    datetime.utcnow() + 
                    timedelta(seconds=self.config.recovery_timeout_seconds)
                )
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state"""
        return self.state

class MetricsCollector:
    """Performance metrics collection"""
    
    def __init__(self, max_metrics_history: int = 10000):
        self.max_metrics_history = max_metrics_history
        self.request_metrics: deque = deque(maxlen=max_metrics_history)
        self.service_counters = defaultdict(lambda: defaultdict(int))
        self.response_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.lock = threading.Lock()
    
    def record_request(self, metrics: RequestMetrics):
        """Record request metrics"""
        with self.lock:
            self.request_metrics.append(metrics)
            
            # Update service counters
            service_counters = self.service_counters[metrics.service_name]
            service_counters['total_requests'] += 1
            
            if 200 <= metrics.status_code < 300:
                service_counters['successful_requests'] += 1
            else:
                service_counters['failed_requests'] += 1
            
            # Track response times
            self.response_times[metrics.service_name].append(metrics.response_time_ms)
    
    def get_service_statistics(self, service_name: str, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get service statistics for specified time window"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        
        with self.lock:
            # Filter metrics by time window
            relevant_metrics = [
                m for m in self.request_metrics 
                if m.service_name == service_name and m.timestamp >= cutoff_time
            ]
            
            if not relevant_metrics:
                return {"service_name": service_name, "no_data": True}
            
            # Calculate statistics
            total_requests = len(relevant_metrics)
            successful_requests = sum(1 for m in relevant_metrics if 200 <= m.status_code < 300)
            failed_requests = total_requests - successful_requests
            
            response_times = [m.response_time_ms for m in relevant_metrics]
            avg_response_time = statistics.mean(response_times)
            
            p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times)
            p99_response_time = statistics.quantiles(response_times, n=100)[98] if len(response_times) >= 100 else max(response_times)
            
            error_rate = (failed_requests / total_requests) * 100 if total_requests > 0 else 0
            
            return {
                "service_name": service_name,
                "time_window_minutes": time_window_minutes,
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "error_rate_percent": error_rate,
                "avg_response_time_ms": avg_response_time,
                "p95_response_time_ms": p95_response_time,
                "p99_response_time_ms": p99_response_time,
                "requests_per_minute": total_requests / time_window_minutes,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_overall_statistics(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get overall system statistics"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        
        with self.lock:
            relevant_metrics = [
                m for m in self.request_metrics 
                if m.timestamp >= cutoff_time
            ]
            
            if not relevant_metrics:
                return {"no_data": True}
            
            # Group by service
            service_stats = {}
            for service_name in set(m.service_name for m in relevant_metrics):
                service_stats[service_name] = self.get_service_statistics(
                    service_name, time_window_minutes
                )
            
            # Overall statistics
            total_requests = len(relevant_metrics)
            total_successful = sum(1 for m in relevant_metrics if 200 <= m.status_code < 300)
            
            return {
                "overall": {
                    "total_requests": total_requests,
                    "successful_requests": total_successful,
                    "failed_requests": total_requests - total_successful,
                    "overall_error_rate_percent": ((total_requests - total_successful) / total_requests) * 100 if total_requests > 0 else 0,
                    "requests_per_minute": total_requests / time_window_minutes,
                    "unique_services": len(service_stats)
                },
                "services": service_stats,
                "timestamp": datetime.utcnow().isoformat()
            }

class MemoryCoordinator:
    """Memory coordination for shared state"""
    
    def __init__(self, namespace: str = "vru-api-orchestration"):
        self.namespace = namespace
        self.memory_store: Dict[str, Any] = {}
        self.expiry_times: Dict[str, datetime] = {}
        self.lock = threading.RLock()
        self.cleanup_task = None
    
    def store(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Store value in memory with optional TTL"""
        with self.lock:
            full_key = f"{self.namespace}:{key}"
            self.memory_store[full_key] = value
            
            if ttl_seconds:
                self.expiry_times[full_key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            elif full_key in self.expiry_times:
                del self.expiry_times[full_key]
    
    def retrieve(self, key: str) -> Any:
        """Retrieve value from memory"""
        with self.lock:
            full_key = f"{self.namespace}:{key}"
            
            # Check if expired
            if full_key in self.expiry_times:
                if datetime.utcnow() > self.expiry_times[full_key]:
                    self.delete(key)
                    return None
            
            return self.memory_store.get(full_key)
    
    def delete(self, key: str):
        """Delete value from memory"""
        with self.lock:
            full_key = f"{self.namespace}:{key}"
            self.memory_store.pop(full_key, None)
            self.expiry_times.pop(full_key, None)
    
    def list_keys(self, pattern: str = None) -> List[str]:
        """List all keys, optionally filtered by pattern"""
        with self.lock:
            namespace_prefix = f"{self.namespace}:"
            keys = [
                key[len(namespace_prefix):] 
                for key in self.memory_store.keys() 
                if key.startswith(namespace_prefix)
            ]
            
            if pattern:
                import fnmatch
                keys = [key for key in keys if fnmatch.fnmatch(key, pattern)]
            
            return keys
    
    def clear_expired(self):
        """Clear expired entries"""
        with self.lock:
            current_time = datetime.utcnow()
            expired_keys = [
                key for key, expiry_time in self.expiry_times.items()
                if current_time > expiry_time
            ]
            
            for key in expired_keys:
                self.memory_store.pop(key, None)
                self.expiry_times.pop(key, None)
            
            return len(expired_keys)
    
    async def start_cleanup_task(self, cleanup_interval_seconds: int = 300):
        """Start automatic cleanup of expired entries"""
        if self.cleanup_task:
            return
        
        self.cleanup_task = asyncio.create_task(
            self._cleanup_loop(cleanup_interval_seconds)
        )
    
    async def stop_cleanup_task(self):
        """Stop cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
    
    async def _cleanup_loop(self, interval_seconds: int):
        """Cleanup loop for expired entries"""
        while True:
            try:
                expired_count = self.clear_expired()
                if expired_count > 0:
                    logger.debug(f"Cleaned up {expired_count} expired entries")
                
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {str(e)}")
                await asyncio.sleep(30)

class ServiceCoordinationMiddleware(BaseHTTPMiddleware):
    """Main service coordination middleware"""
    
    def __init__(self, app, config: Optional[Dict[str, Any]] = None):
        super().__init__(app)
        self.config = config or {}
        
        # Initialize components
        self.service_registry = ServiceRegistry()
        self.load_balancer = LoadBalancer(
            LoadBalancingStrategy(self.config.get("load_balancing_strategy", "health_based"))
        )
        self.metrics_collector = MetricsCollector()
        self.memory_coordinator = MemoryCoordinator()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Configuration
        self.circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=self.config.get("circuit_breaker_failure_threshold", 5),
            recovery_timeout_seconds=self.config.get("circuit_breaker_recovery_timeout", 60)
        )
        
        # Initialize built-in services
        self._register_builtin_services()
    
    def _register_builtin_services(self):
        """Register built-in VRU services"""
        builtin_services = [
            ServiceInstance(
                service_id="ml_inference_engine",
                service_name="ml_inference",
                host="localhost",
                port=8000,
                health_endpoint="/api/v1/health",
                weight=10,
                metadata={"type": "ml", "capability": "yolo_detection"}
            ),
            ServiceInstance(
                service_id="camera_integration_service",
                service_name="camera_integration",
                host="localhost",
                port=8000,
                health_endpoint="/api/v1/camera/status",
                weight=8,
                metadata={"type": "camera", "external_ip": "155.138.239.131"}
            ),
            ServiceInstance(
                service_id="validation_engine",
                service_name="validation",
                host="localhost",
                port=8000,
                health_endpoint="/api/v1/health",
                weight=9,
                metadata={"type": "validation", "capability": "temporal_alignment"}
            ),
            ServiceInstance(
                service_id="project_workflow_manager",
                service_name="project_workflow",
                host="localhost",
                port=8000,
                health_endpoint="/api/v1/health",
                weight=7,
                metadata={"type": "workflow", "capability": "orchestration"}
            )
        ]
        
        for service in builtin_services:
            self.service_registry.register_service(service)
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Main middleware dispatch method"""
        start_time = time.time()
        
        # Determine service from request path
        service_name = self._extract_service_name(request.url.path)
        
        # Get or create circuit breaker for service
        circuit_breaker = self._get_circuit_breaker(service_name)
        
        # Check if request can be processed
        if not circuit_breaker.can_execute():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service unavailable - circuit breaker open",
                    "service": service_name,
                    "retry_after": self.circuit_breaker_config.recovery_timeout_seconds
                }
            )
        
        try:
            # Select service instance
            instances = self.service_registry.get_healthy_instances(service_name)
            if not instances:
                instances = self.service_registry.get_all_instances(service_name)
            
            if not instances:
                circuit_breaker.record_failure()
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "No available service instances",
                        "service": service_name
                    }
                )
            
            selected_instance = self.load_balancer.select_instance(instances)
            if not selected_instance:
                circuit_breaker.record_failure()
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Load balancer failed to select instance",
                        "service": service_name
                    }
                )
            
            # Track connection
            self.load_balancer.increment_connection(selected_instance.service_id)
            
            try:
                # Store service context
                request.state.selected_service = selected_instance
                request.state.service_name = service_name
                
                # Process request
                response = await call_next(request)
                
                # Record success
                circuit_breaker.record_success()
                
                # Calculate response time
                response_time_ms = (time.time() - start_time) * 1000
                
                # Record metrics
                metrics = RequestMetrics(
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    service_name=service_name,
                    timestamp=datetime.utcnow(),
                    client_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    request_size_bytes=len(await request.body()) if hasattr(request, 'body') else 0,
                    response_size_bytes=0  # Would be calculated from response
                )
                
                self.metrics_collector.record_request(metrics)
                
                # Update service metrics in registry
                self.service_registry.update_service_metrics(service_name, {
                    "total_requests": self.service_registry.service_metrics[service_name].total_requests + 1,
                    "avg_response_time_ms": response_time_ms
                })
                
                # Store coordination data in memory
                self.memory_coordinator.store(
                    f"request_metrics:{uuid.uuid4()}",
                    {
                        "service_name": service_name,
                        "response_time_ms": response_time_ms,
                        "status_code": response.status_code,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    ttl_seconds=3600  # 1 hour
                )
                
                return response
                
            finally:
                # Release connection
                self.load_balancer.decrement_connection(selected_instance.service_id)
        
        except Exception as e:
            # Record failure
            circuit_breaker.record_failure()
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Record error metrics
            error_metrics = RequestMetrics(
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                response_time_ms=response_time_ms,
                service_name=service_name,
                timestamp=datetime.utcnow(),
                client_ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )
            
            self.metrics_collector.record_request(error_metrics)
            
            logger.error(f"Service coordination error for {service_name}: {str(e)}")
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Service coordination error",
                    "service": service_name,
                    "message": str(e)
                }
            )
    
    def _extract_service_name(self, path: str) -> str:
        """Extract service name from request path"""
        # Map URL paths to service names
        path_mappings = {
            "/api/v1/ml/": "ml_inference",
            "/api/v1/camera/": "camera_integration",
            "/api/v1/validation/": "validation",
            "/api/v1/projects/": "project_workflow",
            "/api/v1/health": "health"
        }
        
        for path_prefix, service_name in path_mappings.items():
            if path.startswith(path_prefix):
                return service_name
        
        return "unknown"
    
    def _get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(self.circuit_breaker_config)
        return self.circuit_breakers[service_name]
    
    async def start_background_tasks(self):
        """Start background tasks"""
        await self.service_registry.start_health_monitoring()
        await self.memory_coordinator.start_cleanup_task()
        logger.info("Service coordination middleware background tasks started")
    
    async def stop_background_tasks(self):
        """Stop background tasks"""
        await self.service_registry.stop_health_monitoring()
        await self.memory_coordinator.stop_cleanup_task()
        logger.info("Service coordination middleware background tasks stopped")
    
    def get_coordination_status(self) -> Dict[str, Any]:
        """Get comprehensive coordination status"""
        return {
            "services": {
                name: [
                    {
                        "service_id": inst.service_id,
                        "host": inst.host,
                        "port": inst.port,
                        "state": inst.state.value,
                        "response_time_ms": inst.response_time_ms,
                        "weight": inst.weight,
                        "metadata": inst.metadata
                    }
                    for inst in instances
                ]
                for name, instances in self.service_registry.services.items()
            },
            "circuit_breakers": {
                name: breaker.get_state().value
                for name, breaker in self.circuit_breakers.items()
            },
            "load_balancer": {
                "strategy": self.load_balancer.strategy.value,
                "connection_counts": dict(self.load_balancer.connection_counts)
            },
            "memory_coordinator": {
                "namespace": self.memory_coordinator.namespace,
                "stored_keys_count": len(self.memory_coordinator.memory_store),
                "expired_keys_count": len(self.memory_coordinator.expiry_times)
            },
            "timestamp": datetime.utcnow().isoformat()
        }

# Factory function
def create_coordination_middleware(config: Optional[Dict[str, Any]] = None) -> ServiceCoordinationMiddleware:
    """Create service coordination middleware instance"""
    return ServiceCoordinationMiddleware(None, config)

# Default configuration
DEFAULT_CONFIG = {
    "load_balancing_strategy": "health_based",
    "circuit_breaker_failure_threshold": 5,
    "circuit_breaker_recovery_timeout": 60,
    "health_check_interval": 30,
    "metrics_history_size": 10000,
    "memory_cleanup_interval": 300
}