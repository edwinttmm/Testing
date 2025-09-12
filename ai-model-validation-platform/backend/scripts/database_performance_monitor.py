#!/usr/bin/env python3
"""
Database Performance Monitoring Tool

Monitors database performance metrics including:
- Query execution times
- Connection pool utilization
- N+1 query detection
- Connection leak detection
- Performance regression analysis

Author: Performance Monitoring Team
"""

import time
import logging
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Dict, List, Any, Optional
import threading
from collections import defaultdict, deque

# Import application components
from database import engine, get_database_health, get_db
from sqlalchemy import text, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)

class DatabasePerformanceMonitor:
    """Comprehensive database performance monitoring system"""
    
    def __init__(self):
        self.query_logs = deque(maxlen=1000)  # Keep last 1000 queries
        self.connection_events = deque(maxlen=500)  # Keep last 500 connection events
        self.performance_metrics = defaultdict(list)
        self.alert_thresholds = {
            'slow_query_threshold': 2.0,  # seconds
            'high_connection_usage': 0.8,  # 80% of pool size
            'n_plus_one_threshold': 10,  # queries per request
            'connection_leak_threshold': 5  # connections not returned within 5 minutes
        }
        self.monitoring_active = False
        self._setup_monitoring()
    
    def _setup_monitoring(self):
        """Setup SQLAlchemy event listeners for monitoring"""
        
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Track query start time"""
            context._query_start_time = time.time()
            context._query_statement = statement[:200] + "..." if len(statement) > 200 else statement
        
        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Track query completion and performance"""
            if hasattr(context, '_query_start_time'):
                execution_time = time.time() - context._query_start_time
                
                query_info = {
                    'timestamp': datetime.now().isoformat(),
                    'statement': context._query_statement,
                    'execution_time': execution_time,
                    'parameters_count': len(parameters) if parameters else 0,
                    'thread_id': threading.current_thread().ident
                }
                
                self.query_logs.append(query_info)
                
                # Check for slow queries
                if execution_time > self.alert_thresholds['slow_query_threshold']:
                    logger.warning(f"Slow query detected ({execution_time:.3f}s): {context._query_statement}")
                
                # Track performance metrics
                self.performance_metrics['query_times'].append(execution_time)
                if len(self.performance_metrics['query_times']) > 100:
                    self.performance_metrics['query_times'].pop(0)  # Keep only last 100
        
        @event.listens_for(Pool, "connect")
        def pool_connect(dbapi_conn, connection_record):
            """Track connection pool events"""
            event_info = {
                'timestamp': datetime.now().isoformat(),
                'event': 'connect',
                'thread_id': threading.current_thread().ident,
                'connection_id': id(dbapi_conn)
            }
            self.connection_events.append(event_info)
        
        @event.listens_for(Pool, "checkout")
        def pool_checkout(dbapi_conn, connection_record, connection_proxy):
            """Track connection checkout"""
            event_info = {
                'timestamp': datetime.now().isoformat(),
                'event': 'checkout',
                'thread_id': threading.current_thread().ident,
                'connection_id': id(dbapi_conn)
            }
            self.connection_events.append(event_info)
        
        @event.listens_for(Pool, "checkin")
        def pool_checkin(dbapi_conn, connection_record):
            """Track connection checkin"""
            event_info = {
                'timestamp': datetime.now().isoformat(),
                'event': 'checkin',
                'thread_id': threading.current_thread().ident,
                'connection_id': id(dbapi_conn)
            }
            self.connection_events.append(event_info)
        
        logger.info("Database performance monitoring listeners configured")
    
    def start_monitoring(self):
        """Start active performance monitoring"""
        self.monitoring_active = True
        logger.info("Database performance monitoring started")
    
    def stop_monitoring(self):
        """Stop active performance monitoring"""
        self.monitoring_active = False
        logger.info("Database performance monitoring stopped")
    
    def analyze_n_plus_one_queries(self, time_window_seconds: int = 5) -> Dict[str, Any]:
        """Detect potential N+1 query problems"""
        cutoff_time = datetime.now() - timedelta(seconds=time_window_seconds)
        
        # Group queries by thread and time window
        thread_queries = defaultdict(list)
        
        for query_log in self.query_logs:
            query_time = datetime.fromisoformat(query_log['timestamp'])
            if query_time >= cutoff_time:
                thread_id = query_log['thread_id']
                thread_queries[thread_id].append(query_log)
        
        n_plus_one_issues = []
        
        for thread_id, queries in thread_queries.items():
            if len(queries) > self.alert_thresholds['n_plus_one_threshold']:
                # Analyze query patterns
                statement_counts = defaultdict(int)
                for query in queries:
                    # Normalize query by removing specific values
                    normalized = self._normalize_query(query['statement'])
                    statement_counts[normalized] += 1
                
                # Check for repeated similar queries (N+1 pattern)
                for statement, count in statement_counts.items():
                    if count > 3:  # Same query executed more than 3 times
                        n_plus_one_issues.append({
                            'thread_id': thread_id,
                            'statement': statement,
                            'count': count,
                            'total_time': sum(q['execution_time'] for q in queries if self._normalize_query(q['statement']) == statement),
                            'severity': 'high' if count > 10 else 'medium'
                        })
        
        return {
            'issues_found': len(n_plus_one_issues),
            'details': n_plus_one_issues,
            'analysis_window': f"{time_window_seconds} seconds",
            'total_threads_analyzed': len(thread_queries)
        }
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query by removing specific values"""
        import re
        # Remove string literals, numbers, and UUIDs
        normalized = re.sub(r"'[^']*'", "'?'", query)
        normalized = re.sub(r'\\b\\d+\\b', '?', normalized)
        normalized = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '?', normalized, flags=re.IGNORECASE)
        return normalized.strip()
    
    def analyze_connection_pool_health(self) -> Dict[str, Any]:
        """Analyze connection pool health and detect leaks"""
        health = get_database_health()
        
        # Analyze connection events
        recent_events = [
            event for event in self.connection_events
            if datetime.fromisoformat(event['timestamp']) >= datetime.now() - timedelta(minutes=10)
        ]
        
        # Count events by type
        event_counts = defaultdict(int)
        for event in recent_events:
            event_counts[event['event']] += 1
        
        # Detect potential connection leaks
        checkouts = event_counts.get('checkout', 0)
        checkins = event_counts.get('checkin', 0)
        potential_leaks = checkouts - checkins
        
        pool_analysis = {
            'health_status': health.get('status', 'unknown'),
            'pool_size': health.get('pool_size', 'unknown'),
            'checked_out_connections': health.get('checked_out_connections', 'unknown'),
            'recent_activity': {
                'checkouts': checkouts,
                'checkins': checkins,
                'connects': event_counts.get('connect', 0)
            },
            'potential_leaks': potential_leaks,
            'leak_severity': 'high' if potential_leaks > self.alert_thresholds['connection_leak_threshold'] else 'low'
        }
        
        if potential_leaks > 0:
            logger.warning(f"Potential connection leak detected: {potential_leaks} connections may not be properly returned")
        
        return pool_analysis
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        if not self.performance_metrics['query_times']:
            return {'status': 'no_data', 'message': 'No performance data collected yet'}
        
        query_times = self.performance_metrics['query_times']
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'monitoring_status': 'active' if self.monitoring_active else 'inactive',
            'query_performance': {
                'total_queries': len(self.query_logs),
                'avg_execution_time': sum(query_times) / len(query_times),
                'max_execution_time': max(query_times),
                'min_execution_time': min(query_times),
                'slow_queries_count': len([t for t in query_times if t > self.alert_thresholds['slow_query_threshold']])
            },
            'connection_pool': self.analyze_connection_pool_health(),
            'n_plus_one_analysis': self.analyze_n_plus_one_queries(),
            'recommendations': self._generate_recommendations()
        }
        
        return summary
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        if not self.performance_metrics['query_times']:
            return ["Start monitoring to collect performance data"]
        
        query_times = self.performance_metrics['query_times']
        avg_time = sum(query_times) / len(query_times)
        slow_queries = len([t for t in query_times if t > self.alert_thresholds['slow_query_threshold']])
        
        if avg_time > 1.0:
            recommendations.append("Average query time is high - consider query optimization")
        
        if slow_queries > len(query_times) * 0.1:  # More than 10% slow queries
            recommendations.append("High percentage of slow queries detected - review query patterns")
        
        # Check N+1 issues
        n_plus_one = self.analyze_n_plus_one_queries()
        if n_plus_one['issues_found'] > 0:
            recommendations.append(f"N+1 query issues detected - {n_plus_one['issues_found']} potential problems")
        
        # Check connection pool
        pool_health = self.analyze_connection_pool_health()
        if pool_health.get('potential_leaks', 0) > 0:
            recommendations.append("Potential connection leaks detected - ensure proper session management")
        
        if not recommendations:
            recommendations.append("Database performance looks healthy")
        
        return recommendations
    
    @contextmanager
    def performance_test_context(self, test_name: str):
        """Context manager for performance testing"""
        start_time = time.time()
        initial_query_count = len(self.query_logs)
        
        logger.info(f"Starting performance test: {test_name}")
        
        try:
            yield self
        finally:
            end_time = time.time()
            final_query_count = len(self.query_logs)
            
            test_results = {
                'test_name': test_name,
                'duration': end_time - start_time,
                'queries_executed': final_query_count - initial_query_count,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Performance test completed: {test_name}")
            logger.info(f"Duration: {test_results['duration']:.3f}s, Queries: {test_results['queries_executed']}")
    
    def export_metrics(self, filepath: str):
        """Export performance metrics to file"""
        metrics_data = {
            'export_timestamp': datetime.now().isoformat(),
            'query_logs': list(self.query_logs),
            'connection_events': list(self.connection_events),
            'performance_summary': self.get_performance_summary()
        }
        
        with open(filepath, 'w') as f:
            json.dump(metrics_data, f, indent=2, default=str)
        
        logger.info(f"Performance metrics exported to: {filepath}")


# Global monitor instance
db_monitor = DatabasePerformanceMonitor()

def test_optimized_endpoints():
    """Test the optimized endpoints for performance improvements"""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from api_project_session_management import router
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    db_monitor.start_monitoring()
    
    try:
        # Test projects/all endpoint
        with db_monitor.performance_test_context("projects_all_endpoint"):
            for i in range(10):  # Make 10 requests
                response = client.get("/api/project-sessions/projects/all")
                assert response.status_code == 200
        
        # Test statistics/summary endpoint
        with db_monitor.performance_test_context("statistics_summary_endpoint"):
            for i in range(10):  # Make 10 requests
                response = client.get("/api/project-sessions/statistics/summary")
                assert response.status_code == 200
        
        # Analyze results
        summary = db_monitor.get_performance_summary()
        print("\n" + "="*50)
        print("PERFORMANCE OPTIMIZATION RESULTS")
        print("="*50)
        print(json.dumps(summary, indent=2, default=str))
        
        # Export detailed metrics
        db_monitor.export_metrics("/home/rigade/Testing/ai-model-validation-platform/backend/tests/performance_test_results.json")
        
        # Validate optimizations
        n_plus_one = summary['n_plus_one_analysis']
        if n_plus_one['issues_found'] == 0:
            print("✅ N+1 query optimization: SUCCESS")
        else:
            print(f"❌ N+1 query optimization: {n_plus_one['issues_found']} issues found")
        
        pool_health = summary['connection_pool']
        if pool_health['potential_leaks'] == 0:
            print("✅ Connection leak prevention: SUCCESS")
        else:
            print(f"❌ Connection leak prevention: {pool_health['potential_leaks']} potential leaks")
        
    finally:
        db_monitor.stop_monitoring()


if __name__ == "__main__":
    # Run performance optimization tests
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    test_optimized_endpoints()