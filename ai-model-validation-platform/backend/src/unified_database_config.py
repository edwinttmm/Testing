#!/usr/bin/env python3
"""
Unified Database Configuration and Management System

This module provides a comprehensive database configuration system that integrates
all database components into a unified, production-ready solution. It serves as
the main entry point for all database operations across the AI Model Validation Platform.

Key Features:
- Unified configuration management for all environments
- Automatic database type detection and optimization
- Integrated health monitoring and performance tracking
- Automated backup and disaster recovery
- Real-time data integrity monitoring
- Connection pooling and resource management
- Environment-specific optimizations
- Comprehensive logging and diagnostics

Architecture Integration:
- DatabaseArchitecture: Core database management
- UnifiedDatabaseOperations: High-level data operations
- DatabaseMigrationSystem: Schema and data migrations
- Enhanced monitoring and alerting systems
"""

import os
import sys
import json
import logging
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
from enum import Enum

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import database components
from database_architecture import (
    DatabaseArchitecture, DatabaseType, EnvironmentType, DatabaseConfig,
    IntegrityReport, IntegrityStatus, create_database_architecture
)
from database_abstraction import (
    UnifiedDatabaseOperations, QueryOptions, QueryResult,
    create_database_operations
)
from database_migration import (
    DatabaseMigrationSystem, MigrationStatus, MigrationType,
    create_migration_system
)

logger = logging.getLogger(__name__)

class DatabaseHealth(Enum):
    """Overall database health status"""
    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILURE = "failure"

@dataclass
class DatabaseMetrics:
    """Comprehensive database metrics"""
    timestamp: datetime
    health_status: DatabaseHealth
    connection_pool_usage: float
    query_performance_ms: float
    integrity_score: float
    backup_status: str
    active_connections: int
    total_queries: int
    error_rate: float
    storage_usage_mb: float

@dataclass
class DatabaseAlert:
    """Database alert definition"""
    alert_id: str
    severity: str
    title: str
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None

class UnifiedDatabaseManager:
    """
    Comprehensive Database Management System
    
    This class integrates all database components and provides a unified
    interface for database operations, monitoring, and management.
    """
    
    def __init__(
        self,
        connection_string: str,
        database_type: Optional[DatabaseType] = None,
        environment: EnvironmentType = EnvironmentType.DEVELOPMENT
    ):
        self.connection_string = connection_string
        self.database_type = database_type
        self.environment = environment
        
        # Initialize components
        self._initialize_components()
        
        # Monitoring and alerting
        self._metrics_history: List[DatabaseMetrics] = []
        self._active_alerts: List[DatabaseAlert] = []
        self._monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_active = False
        
        # Performance tracking
        self._query_performance_cache: Dict[str, List[float]] = {}
        self._connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "query_count": 0,
            "error_count": 0
        }
        
        logger.info(f"Unified database manager initialized for {self.database_type.value} in {environment.value} mode")
    
    def _initialize_components(self):
        """Initialize all database components"""
        try:
            # Initialize database architecture
            self.db_architecture = create_database_architecture(
                connection_string=self.connection_string,
                database_type=self.database_type,
                environment=self.environment
            )
            
            # Initialize database operations
            self.db_operations = create_database_operations(self.db_architecture)
            
            # Initialize migration system
            self.migration_system = create_migration_system(
                self.db_architecture, 
                self.db_operations
            )
            
            logger.info("All database components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database components: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """Get database session with automatic tracking"""
        self._connection_stats["total_connections"] += 1
        self._connection_stats["active_connections"] += 1
        
        try:
            with self.db_architecture.get_session() as session:
                yield session
        except Exception as e:
            self._connection_stats["error_count"] += 1
            logger.error(f"Session error: {e}")
            raise
        finally:
            self._connection_stats["active_connections"] -= 1
    
    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """Execute query with performance tracking"""
        self._connection_stats["query_count"] += 1
        
        try:
            start_time = datetime.now()
            result = self.db_operations.execute_query(query, params, options)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Track performance
            query_key = query[:50]  # Use first 50 chars as key
            if query_key not in self._query_performance_cache:
                self._query_performance_cache[query_key] = []
            
            self._query_performance_cache[query_key].append(execution_time)
            
            # Keep only last 100 measurements
            if len(self._query_performance_cache[query_key]) > 100:
                self._query_performance_cache[query_key] = self._query_performance_cache[query_key][-100:]
            
            return result
            
        except Exception as e:
            self._connection_stats["error_count"] += 1
            logger.error(f"Query execution failed: {e}")
            raise
    
    def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous database monitoring"""
        if self._monitoring_active:
            logger.warning("Monitoring is already active")
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitoring_thread.start()
        
        logger.info(f"Database monitoring started with {interval_seconds}s interval")
    
    def stop_monitoring(self):
        """Stop database monitoring"""
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        
        logger.info("Database monitoring stopped")
    
    def _monitoring_loop(self, interval_seconds: int):
        """Main monitoring loop"""
        while self._monitoring_active:
            try:
                # Collect metrics
                metrics = self._collect_metrics()
                self._metrics_history.append(metrics)
                
                # Keep only last 24 hours of metrics
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                self._metrics_history = [
                    m for m in self._metrics_history 
                    if m.timestamp >= cutoff_time
                ]
                
                # Check for alerts
                self._check_alerts(metrics)
                
                # Log health status
                if metrics.health_status in [DatabaseHealth.WARNING, DatabaseHealth.CRITICAL]:
                    logger.warning(f"Database health: {metrics.health_status.value}")
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
            
            # Wait for next interval
            for _ in range(interval_seconds):
                if not self._monitoring_active:
                    break
                asyncio.sleep(1) if asyncio.iscoroutinefunction(asyncio.sleep) else None
    
    def _collect_metrics(self) -> DatabaseMetrics:
        """Collect comprehensive database metrics"""
        try:
            # Test connection and get performance metrics
            connection_test = self.db_architecture.test_connection()
            
            # Get integrity report
            integrity_report = self.db_architecture.check_data_integrity()
            
            # Calculate health score
            health_score = self._calculate_health_score(connection_test, integrity_report)
            
            # Get storage usage
            storage_usage = self._get_storage_usage()
            
            # Calculate query performance
            avg_query_time = self._calculate_average_query_time()
            
            # Determine overall health status
            health_status = self._determine_health_status(health_score)
            
            # Calculate pool usage
            pool_usage = self._calculate_pool_usage()
            
            # Calculate error rate
            error_rate = self._calculate_error_rate()
            
            return DatabaseMetrics(
                timestamp=datetime.now(timezone.utc),
                health_status=health_status,
                connection_pool_usage=pool_usage,
                query_performance_ms=avg_query_time,
                integrity_score=health_score,
                backup_status="unknown",  # Would be enhanced with backup status
                active_connections=self._connection_stats["active_connections"],
                total_queries=self._connection_stats["query_count"],
                error_rate=error_rate,
                storage_usage_mb=storage_usage
            )
            
        except Exception as e:
            logger.error(f"Metrics collection failed: {e}")
            return DatabaseMetrics(
                timestamp=datetime.now(timezone.utc),
                health_status=DatabaseHealth.FAILURE,
                connection_pool_usage=0.0,
                query_performance_ms=0.0,
                integrity_score=0.0,
                backup_status="error",
                active_connections=0,
                total_queries=0,
                error_rate=1.0,
                storage_usage_mb=0.0
            )
    
    def _calculate_health_score(self, connection_test: Dict, integrity_report: IntegrityReport) -> float:
        """Calculate overall health score (0-100)"""
        score = 100.0
        
        # Connection test impact (30%)
        if connection_test["status"] != "healthy":
            score -= 30
        
        # Integrity impact (40%)
        if integrity_report.status == IntegrityStatus.CRITICAL:
            score -= 40
        elif integrity_report.status == IntegrityStatus.ERROR:
            score -= 25
        elif integrity_report.status == IntegrityStatus.WARNING:
            score -= 10
        
        # Performance impact (20%)
        avg_query_time = self._calculate_average_query_time()
        if avg_query_time > 1000:  # > 1 second
            score -= 20
        elif avg_query_time > 500:  # > 500ms
            score -= 10
        elif avg_query_time > 200:  # > 200ms
            score -= 5
        
        # Error rate impact (10%)
        error_rate = self._calculate_error_rate()
        if error_rate > 0.1:  # > 10%
            score -= 10
        elif error_rate > 0.05:  # > 5%
            score -= 5
        
        return max(0.0, score)
    
    def _determine_health_status(self, health_score: float) -> DatabaseHealth:
        """Determine health status from score"""
        if health_score >= 95:
            return DatabaseHealth.EXCELLENT
        elif health_score >= 80:
            return DatabaseHealth.GOOD
        elif health_score >= 60:
            return DatabaseHealth.WARNING
        elif health_score >= 30:
            return DatabaseHealth.CRITICAL
        else:
            return DatabaseHealth.FAILURE
    
    def _calculate_average_query_time(self) -> float:
        """Calculate average query execution time"""
        all_times = []
        for times in self._query_performance_cache.values():
            all_times.extend(times)
        
        if not all_times:
            return 0.0
        
        return sum(all_times) / len(all_times)
    
    def _calculate_pool_usage(self) -> float:
        """Calculate connection pool usage percentage"""
        try:
            if hasattr(self.db_architecture.engine, 'pool') and self.db_architecture.engine.pool:
                pool = self.db_architecture.engine.pool
                total_connections = pool.size()
                active_connections = pool.checkedout()
                
                if total_connections > 0:
                    return (active_connections / total_connections) * 100.0
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_error_rate(self) -> float:
        """Calculate query error rate"""
        total_queries = self._connection_stats["query_count"]
        errors = self._connection_stats["error_count"]
        
        if total_queries == 0:
            return 0.0
        
        return errors / total_queries
    
    def _get_storage_usage(self) -> float:
        """Get database storage usage in MB"""
        try:
            if self.database_type == DatabaseType.SQLITE:
                # Get SQLite database file size
                db_path = self.connection_string.replace("sqlite:///", "").replace("sqlite://", "")
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    return size_bytes / (1024 * 1024)  # Convert to MB
            else:
                # PostgreSQL storage would require specific queries
                pass
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Failed to get storage usage: {e}")
            return 0.0
    
    def _check_alerts(self, metrics: DatabaseMetrics):
        """Check for alert conditions and generate alerts"""
        current_time = datetime.now(timezone.utc)
        
        # High error rate alert
        if metrics.error_rate > 0.1:
            self._create_alert(
                "high_error_rate",
                "critical",
                "High Database Error Rate",
                f"Database error rate is {metrics.error_rate:.1%}, exceeding 10% threshold"
            )
        
        # Poor performance alert
        if metrics.query_performance_ms > 1000:
            self._create_alert(
                "slow_queries",
                "warning",
                "Slow Query Performance",
                f"Average query time is {metrics.query_performance_ms:.0f}ms, exceeding 1000ms threshold"
            )
        
        # High pool usage alert
        if metrics.connection_pool_usage > 80:
            self._create_alert(
                "high_pool_usage",
                "warning",
                "High Connection Pool Usage",
                f"Connection pool usage is {metrics.connection_pool_usage:.1f}%, approaching capacity"
            )
        
        # Database health alert
        if metrics.health_status in [DatabaseHealth.CRITICAL, DatabaseHealth.FAILURE]:
            self._create_alert(
                "database_health",
                "critical",
                "Database Health Critical",
                f"Database health status is {metrics.health_status.value}"
            )
    
    def _create_alert(self, alert_id: str, severity: str, title: str, message: str):
        """Create or update an alert"""
        # Check if alert already exists
        existing_alert = next((a for a in self._active_alerts if a.alert_id == alert_id and not a.resolved), None)
        
        if existing_alert:
            # Update existing alert
            existing_alert.message = message
            existing_alert.timestamp = datetime.now(timezone.utc)
        else:
            # Create new alert
            alert = DatabaseAlert(
                alert_id=alert_id,
                severity=severity,
                title=title,
                message=message,
                timestamp=datetime.now(timezone.utc)
            )
            self._active_alerts.append(alert)
            
            # Log alert
            if severity == "critical":
                logger.critical(f"DATABASE ALERT: {title} - {message}")
            else:
                logger.warning(f"DATABASE ALERT: {title} - {message}")
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        try:
            # Get latest metrics
            latest_metrics = self._metrics_history[-1] if self._metrics_history else self._collect_metrics()
            
            # Get connection test results
            connection_test = self.db_architecture.test_connection()
            
            # Get integrity report
            integrity_report = self.db_architecture.check_data_integrity()
            
            # Get migration status
            migration_history = self.migration_system.get_migration_history()
            pending_migrations = self.migration_system.get_pending_migrations()
            
            # Get performance statistics
            performance_stats = self._get_performance_statistics()
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_health": latest_metrics.health_status.value,
                "health_score": latest_metrics.integrity_score,
                "database_type": self.database_type.value,
                "environment": self.environment.value,
                "connection_status": connection_test["status"],
                "integrity_status": integrity_report.status.value,
                "metrics": {
                    "active_connections": latest_metrics.active_connections,
                    "total_queries": latest_metrics.total_queries,
                    "error_rate": latest_metrics.error_rate,
                    "avg_query_time_ms": latest_metrics.query_performance_ms,
                    "storage_usage_mb": latest_metrics.storage_usage_mb,
                    "pool_usage_percent": latest_metrics.connection_pool_usage
                },
                "migrations": {
                    "applied": len(migration_history),
                    "pending": len(pending_migrations),
                    "last_migration": migration_history[0].migration_version if migration_history else None
                },
                "performance": performance_stats,
                "active_alerts": [
                    {
                        "id": alert.alert_id,
                        "severity": alert.severity,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat()
                    }
                    for alert in self._active_alerts if not alert.resolved
                ],
                "uptime_info": {
                    "monitoring_active": self._monitoring_active,
                    "metrics_collected": len(self._metrics_history)
                }
            }
            
        except Exception as e:
            logger.error(f"Health report generation failed: {e}")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_health": "error",
                "error": str(e)
            }
    
    def _get_performance_statistics(self) -> Dict[str, Any]:
        """Get detailed performance statistics"""
        stats = {
            "query_types": {},
            "slowest_queries": [],
            "error_patterns": {},
            "performance_trends": {}
        }
        
        try:
            # Analyze query performance cache
            for query_key, times in self._query_performance_cache.items():
                if times:
                    stats["query_types"][query_key] = {
                        "count": len(times),
                        "avg_time_ms": sum(times) / len(times),
                        "max_time_ms": max(times),
                        "min_time_ms": min(times)
                    }
            
            # Find slowest queries
            slowest = sorted(
                stats["query_types"].items(),
                key=lambda x: x[1]["avg_time_ms"],
                reverse=True
            )[:5]
            
            stats["slowest_queries"] = [
                {"query": query, "avg_time_ms": data["avg_time_ms"]}
                for query, data in slowest
            ]
            
        except Exception as e:
            logger.warning(f"Performance statistics calculation failed: {e}")
        
        return stats
    
    def optimize_performance(self) -> Dict[str, Any]:
        """Run performance optimization"""
        try:
            # Run database-specific optimizations
            optimization_result = self.db_architecture.optimize_performance()
            
            # Clear performance cache to get fresh metrics
            self._query_performance_cache.clear()
            
            logger.info("Database performance optimization completed")
            return optimization_result
            
        except Exception as e:
            logger.error(f"Performance optimization failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """Create database backup"""
        try:
            backup_result = self.db_architecture.backup_database(backup_name)
            
            if backup_result["status"] == "success":
                logger.info(f"Database backup created: {backup_result['backup_path']}")
            
            return backup_result
            
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def run_integrity_check(self, repair: bool = False) -> IntegrityReport:
        """Run comprehensive data integrity check"""
        try:
            integrity_report = self.db_architecture.check_data_integrity(repair=repair)
            
            if integrity_report.status != IntegrityStatus.HEALTHY:
                logger.warning(f"Data integrity issues found: {integrity_report.status.value}")
            
            return integrity_report
            
        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            # Return error report
            return IntegrityReport(
                status=IntegrityStatus.CRITICAL,
                timestamp=datetime.now(timezone.utc),
                total_checks=0,
                passed_checks=0,
                failed_checks=1,
                errors=[str(e)]
            )
    
    def shutdown(self):
        """Gracefully shutdown database manager"""
        try:
            # Stop monitoring
            self.stop_monitoring()
            
            # Shutdown database architecture
            self.db_architecture.shutdown()
            
            logger.info("Database manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics"""
        return {
            "connection_stats": self._connection_stats.copy(),
            "metrics_history_count": len(self._metrics_history),
            "active_alerts_count": len([a for a in self._active_alerts if not a.resolved]),
            "monitoring_active": self._monitoring_active,
            "query_cache_size": len(self._query_performance_cache),
            "database_operations_stats": self.db_operations.get_statistics()
        }


# Factory functions
def create_unified_database_manager(
    connection_string: str,
    database_type: Optional[DatabaseType] = None,
    environment: EnvironmentType = EnvironmentType.DEVELOPMENT
) -> UnifiedDatabaseManager:
    """Create unified database manager instance"""
    return UnifiedDatabaseManager(connection_string, database_type, environment)


def get_unified_database_manager() -> UnifiedDatabaseManager:
    """Get global unified database manager instance"""
    try:
        # Import settings from config
        from config import settings
        
        # Determine environment
        env_mapping = {
            "development": EnvironmentType.DEVELOPMENT,
            "testing": EnvironmentType.TESTING,
            "production": EnvironmentType.PRODUCTION
        }
        environment = env_mapping.get(settings.app_environment.lower(), EnvironmentType.DEVELOPMENT)
        
        return create_unified_database_manager(
            connection_string=settings.database_url,
            environment=environment
        )
        
    except Exception as e:
        logger.error(f"Failed to create unified database manager: {e}")
        raise


if __name__ == "__main__":
    # CLI for unified database management
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified Database Management")
    parser.add_argument("--health", action="store_true", help="Get health report")
    parser.add_argument("--monitor", type=int, default=0, help="Start monitoring (interval in seconds)")
    parser.add_argument("--backup", type=str, nargs="?", const="auto", help="Create backup")
    parser.add_argument("--integrity", action="store_true", help="Run integrity check")
    parser.add_argument("--repair", action="store_true", help="Repair integrity issues")
    parser.add_argument("--optimize", action="store_true", help="Optimize performance")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    
    args = parser.parse_args()
    
    try:
        db_manager = get_unified_database_manager()
        
        if args.health:
            health_report = db_manager.get_health_report()
            print(json.dumps(health_report, indent=2, default=str))
        
        elif args.monitor:
            print(f"Starting database monitoring with {args.monitor}s interval...")
            db_manager.start_monitoring(args.monitor)
            
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping monitoring...")
                db_manager.stop_monitoring()
        
        elif args.backup:
            backup_name = args.backup if args.backup != "auto" else None
            result = db_manager.create_backup(backup_name)
            print(json.dumps(result, indent=2, default=str))
        
        elif args.integrity:
            report = db_manager.run_integrity_check(repair=args.repair)
            print(f"Integrity Status: {report.status.value}")
            print(f"Checks: {report.passed_checks}/{report.total_checks} passed")
            if report.errors:
                print("Errors:")
                for error in report.errors:
                    print(f"  - {error}")
        
        elif args.optimize:
            result = db_manager.optimize_performance()
            print(json.dumps(result, indent=2, default=str))
        
        elif args.stats:
            stats = db_manager.get_statistics()
            print(json.dumps(stats, indent=2, default=str))
        
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
    finally:
        try:
            if 'db_manager' in locals():
                db_manager.shutdown()
        except:
            pass