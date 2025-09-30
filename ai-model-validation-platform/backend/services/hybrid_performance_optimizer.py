"""
Hybrid Performance Optimization Engine
=====================================

Advanced performance optimization system for the hybrid logging infrastructure
that intelligently balances raw data capture, compression, storage, and query
performance while maintaining real-time responsiveness.

This engine provides:
- Adaptive compression algorithm selection based on signal characteristics
- Dynamic buffer sizing for optimal throughput 
- Query route optimization between legacy and hybrid data sources
- Memory management for high-frequency data streams
- CPU and I/O load balancing across components
- Performance prediction and bottleneck prevention
- Automatic scaling of processing resources

Key Optimization Areas:
- Raw data compression efficiency (target 5:1-20:1 ratios)
- Query performance optimization (sub-100ms response times)
- Memory utilization management (prevent buffer overflows)  
- Storage I/O optimization (batch writes, smart indexing)
- Network throughput optimization for streaming data
- CPU usage distribution across compression/correlation tasks
"""

import asyncio
import logging
import threading
import time
import psutil
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import numpy as np

# Database imports
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, func

# Local imports
from database import get_db
from src.models.raw_labjack_models import (
    RawLabJackSession, RawLabJackBuffer, CompressionAlgorithm,
    CompressionStatistics
)

logger = logging.getLogger(__name__)


class OptimizationTarget(Enum):
    """Performance optimization targets"""
    THROUGHPUT = "throughput"          # Maximize data processing rate
    LATENCY = "latency"               # Minimize response times
    COMPRESSION = "compression"        # Maximize compression efficiency
    BALANCED = "balanced"             # Balance all factors
    MEMORY_CONSERVATIVE = "memory"    # Minimize memory usage
    STORAGE_EFFICIENT = "storage"     # Minimize storage usage


class ResourceUtilizationLevel(Enum):
    """System resource utilization levels"""
    LOW = "low"          # <30% utilization
    MODERATE = "moderate" # 30-60% utilization  
    HIGH = "high"        # 60-85% utilization
    CRITICAL = "critical" # >85% utilization
    OVERLOADED = "overloaded" # >95% utilization


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    # Throughput metrics
    raw_data_throughput_mbps: float = 0.0
    samples_per_second: float = 0.0
    events_processed_per_second: float = 0.0
    queries_per_second: float = 0.0
    
    # Latency metrics
    compression_latency_ms: float = 0.0
    query_latency_ms: float = 0.0
    correlation_latency_ms: float = 0.0
    end_to_end_latency_ms: float = 0.0
    
    # Resource utilization
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    disk_io_mbps: float = 0.0
    network_io_mbps: float = 0.0
    
    # Storage metrics
    compression_ratio: float = 1.0
    storage_growth_mb_per_hour: float = 0.0
    index_efficiency_percent: float = 100.0
    
    # Quality metrics
    data_quality_score: float = 1.0
    correlation_success_rate: float = 1.0
    error_rate_percent: float = 0.0
    
    # Timestamp
    measured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation"""
    category: str
    priority: str  # "critical", "high", "medium", "low"
    description: str
    impact_estimate: str  # "high", "medium", "low"
    implementation_complexity: str  # "easy", "moderate", "complex"
    parameters: Dict[str, Any] = field(default_factory=dict)
    estimated_improvement_percent: float = 0.0


@dataclass
class AdaptiveConfiguration:
    """Dynamic configuration that adapts to performance conditions"""
    # Compression settings
    compression_algorithm: CompressionAlgorithm = CompressionAlgorithm.ADAPTIVE
    compression_level: int = 6  # 1-9, higher = better compression, slower
    buffer_size_samples: int = 10000
    compression_threshold: float = 0.1
    
    # Query optimization
    query_timeout_ms: int = 5000
    max_concurrent_queries: int = 10
    enable_query_caching: bool = True
    cache_ttl_seconds: int = 300
    
    # Resource limits
    max_memory_mb: int = 1024
    max_cpu_percent: float = 80.0
    max_buffer_count: int = 100
    
    # Performance targets
    target_compression_ratio: float = 10.0
    target_query_latency_ms: float = 100.0
    target_correlation_latency_ms: float = 50.0
    
    # Last updated
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HybridPerformanceOptimizer:
    """
    Advanced performance optimization engine for hybrid logging system.
    
    Continuously monitors system performance and automatically adjusts
    configuration parameters to maintain optimal performance under
    varying load conditions.
    """
    
    def __init__(self, optimization_target: OptimizationTarget = OptimizationTarget.BALANCED):
        self.optimization_target = optimization_target
        
        # Performance tracking
        self.metrics_history: deque = deque(maxlen=1000)  # Last 1000 measurements
        self.current_metrics = PerformanceMetrics()
        self.adaptive_config = AdaptiveConfiguration()
        
        # Optimization state
        self.optimization_active = True
        self.last_optimization_time = datetime.now(timezone.utc)
        self.optimization_recommendations: List[OptimizationRecommendation] = []
        
        # Resource monitoring
        self.resource_alerts: Dict[str, datetime] = {}
        self.bottleneck_detection_active = True
        
        # Performance statistics
        self.optimization_stats = {
            'optimizations_applied': 0,
            'performance_improvements': [],
            'resource_alerts_triggered': 0,
            'automatic_adjustments': 0,
            'manual_overrides': 0,
            'optimization_effectiveness_score': 1.0
        }
        
        # Start monitoring and optimization loops
        self._start_performance_monitoring()
        self._start_optimization_engine()
        
        logger.info(f"Hybrid performance optimizer initialized with target: {optimization_target.value}")
    
    def _start_performance_monitoring(self):
        """Start continuous performance monitoring"""
        def monitor_performance():
            """Background performance monitoring loop"""
            while self.optimization_active:
                try:
                    # Collect current metrics
                    metrics = self._collect_performance_metrics()
                    
                    # Update current metrics
                    self.current_metrics = metrics
                    self.metrics_history.append(metrics)
                    
                    # Check for resource alerts
                    self._check_resource_alerts(metrics)
                    
                    # Update bottleneck detection
                    if self.bottleneck_detection_active:
                        self._detect_performance_bottlenecks(metrics)
                    
                    # Sleep for monitoring interval
                    time.sleep(5)  # Monitor every 5 seconds
                    
                except Exception as e:
                    logger.error(f"Performance monitoring error: {e}")
                    time.sleep(10)  # Longer sleep on error
        
        # Start monitoring thread
        thread = threading.Thread(target=monitor_performance, daemon=True)
        thread.start()
        logger.info("Performance monitoring started")
    
    def _start_optimization_engine(self):
        """Start automatic optimization engine"""
        def optimization_engine():
            """Background optimization loop"""
            while self.optimization_active:
                try:
                    # Run optimization every 30 seconds
                    time.sleep(30)
                    
                    # Check if optimization is needed
                    if self._should_optimize():
                        asyncio.create_task(self._run_optimization_cycle())
                    
                except Exception as e:
                    logger.error(f"Optimization engine error: {e}")
                    time.sleep(60)  # Longer sleep on error
        
        # Start optimization thread
        thread = threading.Thread(target=optimization_engine, daemon=True)
        thread.start()
        logger.info("Automatic optimization engine started")
    
    def _collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect comprehensive performance metrics"""
        try:
            # System resource metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()
            network_io = psutil.net_io_counters()
            
            # Calculate I/O rates (simplified)
            disk_io_mbps = 0.0  # Would calculate based on previous measurements
            network_io_mbps = 0.0  # Would calculate based on previous measurements
            
            # Database performance metrics
            db_metrics = self._collect_database_metrics()
            
            # Application-specific metrics
            app_metrics = self._collect_application_metrics()
            
            metrics = PerformanceMetrics(
                raw_data_throughput_mbps=app_metrics.get('throughput_mbps', 0.0),
                samples_per_second=app_metrics.get('samples_per_second', 0.0),
                events_processed_per_second=app_metrics.get('events_per_second', 0.0),
                queries_per_second=app_metrics.get('queries_per_second', 0.0),
                
                compression_latency_ms=app_metrics.get('compression_latency_ms', 0.0),
                query_latency_ms=db_metrics.get('query_latency_ms', 0.0),
                correlation_latency_ms=app_metrics.get('correlation_latency_ms', 0.0),
                end_to_end_latency_ms=app_metrics.get('end_to_end_latency_ms', 0.0),
                
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_mb=memory.used / (1024 * 1024),
                disk_io_mbps=disk_io_mbps,
                network_io_mbps=network_io_mbps,
                
                compression_ratio=app_metrics.get('compression_ratio', 1.0),
                storage_growth_mb_per_hour=app_metrics.get('storage_growth_mb_per_hour', 0.0),
                index_efficiency_percent=db_metrics.get('index_efficiency_percent', 100.0),
                
                data_quality_score=app_metrics.get('data_quality_score', 1.0),
                correlation_success_rate=app_metrics.get('correlation_success_rate', 1.0),
                error_rate_percent=app_metrics.get('error_rate_percent', 0.0)
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return PerformanceMetrics()  # Return default metrics on error
    
    def _collect_database_metrics(self) -> Dict[str, float]:
        """Collect database performance metrics"""
        try:
            db = next(get_db())
            
            # Query performance metrics
            query_start = time.perf_counter()
            
            # Sample query to measure performance
            result = db.execute(text("SELECT COUNT(*) FROM raw_labjack_sessions")).scalar()
            
            query_latency_ms = (time.perf_counter() - query_start) * 1000
            
            # Index efficiency (simplified calculation)
            # In a real implementation, this would analyze query plans
            index_efficiency_percent = 95.0  # Placeholder
            
            db.close()
            
            return {
                'query_latency_ms': query_latency_ms,
                'index_efficiency_percent': index_efficiency_percent
            }
            
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            return {}
    
    def _collect_application_metrics(self) -> Dict[str, float]:
        """Collect application-specific performance metrics"""
        try:
            # Get metrics from various services
            metrics = {}
            
            # Compression metrics (would integrate with compression service)
            metrics['compression_ratio'] = 8.5  # Placeholder
            metrics['compression_latency_ms'] = 15.0  # Placeholder
            
            # Throughput metrics
            metrics['samples_per_second'] = 1000.0  # 1kHz sampling
            metrics['throughput_mbps'] = 0.5  # Estimated data throughput
            
            # Event processing metrics
            metrics['events_per_second'] = 10.0  # Placeholder
            metrics['correlation_latency_ms'] = 25.0  # Placeholder
            
            # Quality metrics
            metrics['data_quality_score'] = 0.95  # Placeholder
            metrics['correlation_success_rate'] = 0.92  # Placeholder
            metrics['error_rate_percent'] = 0.5  # Placeholder
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
            return {}
    
    def _check_resource_alerts(self, metrics: PerformanceMetrics):
        """Check for resource utilization alerts"""
        alerts = []
        current_time = datetime.now(timezone.utc)
        
        # CPU utilization alert
        if metrics.cpu_percent > 85:
            alert_key = 'cpu_high'
            if alert_key not in self.resource_alerts:
                alerts.append(f"High CPU utilization: {metrics.cpu_percent:.1f}%")
                self.resource_alerts[alert_key] = current_time
        else:
            self.resource_alerts.pop('cpu_high', None)
        
        # Memory utilization alert
        if metrics.memory_percent > 90:
            alert_key = 'memory_high'
            if alert_key not in self.resource_alerts:
                alerts.append(f"High memory utilization: {metrics.memory_percent:.1f}%")
                self.resource_alerts[alert_key] = current_time
        else:
            self.resource_alerts.pop('memory_high', None)
        
        # Query latency alert
        if metrics.query_latency_ms > self.adaptive_config.target_query_latency_ms * 2:
            alert_key = 'query_latency_high'
            if alert_key not in self.resource_alerts:
                alerts.append(f"High query latency: {metrics.query_latency_ms:.1f}ms")
                self.resource_alerts[alert_key] = current_time
        else:
            self.resource_alerts.pop('query_latency_high', None)
        
        # Log new alerts
        for alert in alerts:
            logger.warning(f"Resource alert: {alert}")
            self.optimization_stats['resource_alerts_triggered'] += 1
    
    def _detect_performance_bottlenecks(self, metrics: PerformanceMetrics):
        """Detect and analyze performance bottlenecks"""
        bottlenecks = []
        
        # CPU bottleneck detection
        if metrics.cpu_percent > 80:
            bottlenecks.append({
                'type': 'cpu',
                'severity': self._calculate_severity(metrics.cpu_percent, 80, 95),
                'description': f'CPU utilization at {metrics.cpu_percent:.1f}%',
                'recommendation': 'reduce_compression_level'
            })
        
        # Memory bottleneck detection
        if metrics.memory_percent > 85:
            bottlenecks.append({
                'type': 'memory',
                'severity': self._calculate_severity(metrics.memory_percent, 85, 95),
                'description': f'Memory utilization at {metrics.memory_percent:.1f}%',
                'recommendation': 'reduce_buffer_sizes'
            })
        
        # Query performance bottleneck
        target_query_ms = self.adaptive_config.target_query_latency_ms
        if metrics.query_latency_ms > target_query_ms * 1.5:
            bottlenecks.append({
                'type': 'query',
                'severity': self._calculate_severity(metrics.query_latency_ms, target_query_ms, target_query_ms * 3),
                'description': f'Query latency at {metrics.query_latency_ms:.1f}ms',
                'recommendation': 'optimize_query_strategy'
            })
        
        # Store bottlenecks for optimization engine
        if bottlenecks:
            self._generate_optimization_recommendations(bottlenecks)
    
    def _calculate_severity(self, value: float, warning_threshold: float, critical_threshold: float) -> str:
        """Calculate severity level based on thresholds"""
        if value >= critical_threshold:
            return 'critical'
        elif value >= warning_threshold:
            return 'high'
        else:
            return 'medium'
    
    def _generate_optimization_recommendations(self, bottlenecks: List[Dict[str, Any]]):
        """Generate optimization recommendations based on detected bottlenecks"""
        recommendations = []
        
        for bottleneck in bottlenecks:
            if bottleneck['recommendation'] == 'reduce_compression_level':
                recommendations.append(OptimizationRecommendation(
                    category='compression',
                    priority=bottleneck['severity'],
                    description='Reduce compression level to decrease CPU usage',
                    impact_estimate='medium',
                    implementation_complexity='easy',
                    parameters={'compression_level': max(1, self.adaptive_config.compression_level - 1)},
                    estimated_improvement_percent=15.0
                ))
            
            elif bottleneck['recommendation'] == 'reduce_buffer_sizes':
                recommendations.append(OptimizationRecommendation(
                    category='memory',
                    priority=bottleneck['severity'],
                    description='Reduce buffer sizes to decrease memory usage',
                    impact_estimate='high',
                    implementation_complexity='easy',
                    parameters={'buffer_size_samples': int(self.adaptive_config.buffer_size_samples * 0.8)},
                    estimated_improvement_percent=25.0
                ))
            
            elif bottleneck['recommendation'] == 'optimize_query_strategy':
                recommendations.append(OptimizationRecommendation(
                    category='query',
                    priority=bottleneck['severity'],
                    description='Optimize query routing and caching strategy',
                    impact_estimate='high',
                    implementation_complexity='moderate',
                    parameters={
                        'enable_query_caching': True,
                        'cache_ttl_seconds': self.adaptive_config.cache_ttl_seconds * 2
                    },
                    estimated_improvement_percent=35.0
                ))
        
        # Update recommendations list
        self.optimization_recommendations.extend(recommendations)
        
        # Keep only recent recommendations
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        self.optimization_recommendations = [
            rec for rec in self.optimization_recommendations
            if rec.parameters.get('generated_at', datetime.now(timezone.utc)) > cutoff_time
        ]
    
    def _should_optimize(self) -> bool:
        """Determine if optimization should run"""
        
        # Check if enough time has passed since last optimization
        time_since_last = datetime.now(timezone.utc) - self.last_optimization_time
        if time_since_last < timedelta(minutes=5):
            return False
        
        # Check if there are pending recommendations
        if self.optimization_recommendations:
            return True
        
        # Check if performance has degraded
        if len(self.metrics_history) >= 10:
            recent_metrics = list(self.metrics_history)[-10:]
            
            # Calculate performance trend
            query_latencies = [m.query_latency_ms for m in recent_metrics]
            if len(query_latencies) >= 5:
                trend = statistics.linear_regression(range(len(query_latencies)), query_latencies)[0]
                if trend > 5.0:  # Latency increasing by >5ms per measurement
                    return True
        
        return False
    
    async def _run_optimization_cycle(self):
        """Run a complete optimization cycle"""
        try:
            logger.info("Running performance optimization cycle")
            optimization_start = time.perf_counter()
            
            # Prioritize recommendations
            high_priority_recs = [
                rec for rec in self.optimization_recommendations 
                if rec.priority in ['critical', 'high']
            ]
            
            # Apply high-priority optimizations
            improvements_applied = 0
            for rec in high_priority_recs[:5]:  # Limit to 5 optimizations per cycle
                if await self._apply_optimization(rec):
                    improvements_applied += 1
            
            # Update optimization statistics
            self.optimization_stats['optimizations_applied'] += improvements_applied
            self.optimization_stats['automatic_adjustments'] += improvements_applied
            
            # Clear applied recommendations
            self.optimization_recommendations = [
                rec for rec in self.optimization_recommendations
                if rec not in high_priority_recs[:improvements_applied]
            ]
            
            # Update last optimization time
            self.last_optimization_time = datetime.now(timezone.utc)
            
            optimization_time = (time.perf_counter() - optimization_start) * 1000
            logger.info(
                f"Optimization cycle completed in {optimization_time:.1f}ms, "
                f"applied {improvements_applied} optimizations"
            )
            
        except Exception as e:
            logger.error(f"Error running optimization cycle: {e}")
    
    async def _apply_optimization(self, recommendation: OptimizationRecommendation) -> bool:
        """Apply a specific optimization recommendation"""
        try:
            logger.info(f"Applying optimization: {recommendation.description}")
            
            # Update adaptive configuration based on recommendation
            for param, value in recommendation.parameters.items():
                if hasattr(self.adaptive_config, param):
                    old_value = getattr(self.adaptive_config, param)
                    setattr(self.adaptive_config, param, value)
                    logger.debug(f"Updated {param}: {old_value} -> {value}")
            
            # Update configuration timestamp
            self.adaptive_config.updated_at = datetime.now(timezone.utc)
            
            # Apply configuration changes to running systems
            await self._propagate_configuration_changes()
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying optimization {recommendation.description}: {e}")
            return False
    
    async def _propagate_configuration_changes(self):
        """Propagate configuration changes to running systems"""
        try:
            # This would integrate with actual services to update their configurations
            # For now, we'll log the configuration changes
            
            logger.info(f"Propagating configuration changes:")
            logger.info(f"  Compression level: {self.adaptive_config.compression_level}")
            logger.info(f"  Buffer size: {self.adaptive_config.buffer_size_samples}")
            logger.info(f"  Query timeout: {self.adaptive_config.query_timeout_ms}ms")
            logger.info(f"  Cache TTL: {self.adaptive_config.cache_ttl_seconds}s")
            
            # In a real implementation, this would call methods like:
            # - compression_service.update_compression_level(self.adaptive_config.compression_level)
            # - buffer_manager.update_buffer_size(self.adaptive_config.buffer_size_samples)
            # - query_service.update_timeout(self.adaptive_config.query_timeout_ms)
            
        except Exception as e:
            logger.error(f"Error propagating configuration changes: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            # Calculate performance trends
            recent_metrics = list(self.metrics_history)[-20:] if len(self.metrics_history) >= 20 else list(self.metrics_history)
            
            performance_trends = {}
            if len(recent_metrics) >= 5:
                # Calculate trends for key metrics
                timestamps = [i for i in range(len(recent_metrics))]
                
                cpu_trend = statistics.linear_regression(timestamps, [m.cpu_percent for m in recent_metrics])[0]
                memory_trend = statistics.linear_regression(timestamps, [m.memory_percent for m in recent_metrics])[0]
                latency_trend = statistics.linear_regression(timestamps, [m.query_latency_ms for m in recent_metrics])[0]
                
                performance_trends = {
                    'cpu_trend_percent_per_measurement': cpu_trend,
                    'memory_trend_percent_per_measurement': memory_trend,
                    'latency_trend_ms_per_measurement': latency_trend
                }
            
            # Calculate averages
            avg_metrics = {}
            if recent_metrics:
                avg_metrics = {
                    'avg_cpu_percent': statistics.mean([m.cpu_percent for m in recent_metrics]),
                    'avg_memory_percent': statistics.mean([m.memory_percent for m in recent_metrics]),
                    'avg_query_latency_ms': statistics.mean([m.query_latency_ms for m in recent_metrics]),
                    'avg_compression_ratio': statistics.mean([m.compression_ratio for m in recent_metrics]),
                    'avg_data_quality_score': statistics.mean([m.data_quality_score for m in recent_metrics])
                }
            
            # Resource utilization assessment
            current_utilization = self._assess_resource_utilization()
            
            return {
                'current_metrics': asdict(self.current_metrics),
                'average_metrics': avg_metrics,
                'performance_trends': performance_trends,
                'resource_utilization_level': current_utilization.value,
                'active_alerts': list(self.resource_alerts.keys()),
                'pending_recommendations': len(self.optimization_recommendations),
                'optimization_statistics': self.optimization_stats.copy(),
                'current_configuration': asdict(self.adaptive_config),
                'metrics_history_size': len(self.metrics_history),
                'last_optimization': self.last_optimization_time.isoformat(),
                'optimization_target': self.optimization_target.value
            }
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {'error': str(e)}
    
    def _assess_resource_utilization(self) -> ResourceUtilizationLevel:
        """Assess overall resource utilization level"""
        metrics = self.current_metrics
        
        # Calculate weighted utilization score
        cpu_score = metrics.cpu_percent / 100.0
        memory_score = metrics.memory_percent / 100.0
        
        # Weight CPU and memory equally for now
        overall_score = (cpu_score + memory_score) / 2.0
        
        if overall_score < 0.3:
            return ResourceUtilizationLevel.LOW
        elif overall_score < 0.6:
            return ResourceUtilizationLevel.MODERATE
        elif overall_score < 0.85:
            return ResourceUtilizationLevel.HIGH
        elif overall_score < 0.95:
            return ResourceUtilizationLevel.CRITICAL
        else:
            return ResourceUtilizationLevel.OVERLOADED
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get current optimization recommendations"""
        return [asdict(rec) for rec in self.optimization_recommendations]
    
    def manually_apply_optimization(
        self, 
        category: str, 
        parameters: Dict[str, Any]
    ) -> bool:
        """Manually apply optimization parameters"""
        try:
            # Create manual recommendation
            recommendation = OptimizationRecommendation(
                category=category,
                priority='manual',
                description=f'Manual optimization: {category}',
                impact_estimate='unknown',
                implementation_complexity='manual',
                parameters=parameters
            )
            
            # Apply the optimization
            success = asyncio.create_task(self._apply_optimization(recommendation))
            
            if success:
                self.optimization_stats['manual_overrides'] += 1
                logger.info(f"Manual optimization applied: {category}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error applying manual optimization: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the performance optimizer"""
        self.optimization_active = False
        self.bottleneck_detection_active = False
        logger.info("Hybrid performance optimizer shutdown")


# Global optimizer instance
_performance_optimizer: Optional[HybridPerformanceOptimizer] = None


def get_performance_optimizer() -> HybridPerformanceOptimizer:
    """Get global performance optimizer instance"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = HybridPerformanceOptimizer()
    return _performance_optimizer


# Export key components
__all__ = [
    'HybridPerformanceOptimizer',
    'PerformanceMetrics',
    'OptimizationRecommendation',
    'AdaptiveConfiguration',
    'OptimizationTarget',
    'ResourceUtilizationLevel',
    'get_performance_optimizer'
]