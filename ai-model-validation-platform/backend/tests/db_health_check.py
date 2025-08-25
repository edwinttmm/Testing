#!/usr/bin/env python3
"""
PostgreSQL Health Check Script - Comprehensive Database Connectivity Testing

This script provides detailed diagnostics for PostgreSQL container health,
network connectivity, and database initialization validation.

Features:
- Container health monitoring
- Network connectivity testing
- Database initialization verification
- Connection pool monitoring
- Real-time health status reporting
- Automated recovery suggestions
"""

import os
import sys
import time
import json
import psutil
import docker
import logging
import psycopg2
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add backend directory to path for imports
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')

try:
    from sqlalchemy import create_engine, text, inspect
    from database import get_database_health, engine, DATABASE_URL
except ImportError:
    print("Warning: Could not import database modules. Some features may be limited.")
    engine = None
    DATABASE_URL = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/home/user/Testing/ai-model-validation-platform/backend/logs/db_health.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class HealthStatus:
    """Health status data structure"""
    timestamp: str
    component: str
    status: str
    details: Dict
    error: Optional[str] = None
    suggestions: List[str] = None

class PostgreSQLHealthChecker:
    """Comprehensive PostgreSQL health monitoring system"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._load_default_config()
        self.docker_client = None
        self.monitoring = False
        self.health_history = []
        self.alerts = []
        
        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Docker client initialization failed: {e}")
    
    def _load_default_config(self) -> Dict:
        """Load default configuration from environment"""
        return {
            'postgres_container': 'postgres',
            'backend_container': 'backend',
            'redis_container': 'redis',
            'network_name': 'vru_validation_network',
            'db_host': os.getenv('DATABASE_HOST', 'localhost'),
            'db_port': int(os.getenv('DATABASE_PORT', '5432')),
            'db_name': os.getenv('POSTGRES_DB', 'vru_validation'),
            'db_user': os.getenv('POSTGRES_USER', 'postgres'),
            'db_password': os.getenv('POSTGRES_PASSWORD', 'secure_password_change_me'),
            'health_check_interval': 30,
            'connection_timeout': 10,
            'max_retry_attempts': 5,
            'expected_tables': [
                'projects', 'videos', 'ground_truth_objects', 'test_sessions',
                'detection_events', 'annotations', 'annotation_sessions',
                'validation_results', 'model_versions', 'video_project_links',
                'system_config'
            ]
        }
    
    def check_docker_container_health(self, container_name: str) -> HealthStatus:
        """Check Docker container health status"""
        try:
            if not self.docker_client:
                return HealthStatus(
                    timestamp=datetime.now().isoformat(),
                    component=f'docker_{container_name}',
                    status='error',
                    details={},
                    error='Docker client not available',
                    suggestions=['Install Docker', 'Check Docker daemon status']
                )
            
            # Get container
            try:
                container = self.docker_client.containers.get(container_name)
            except docker.errors.NotFound:
                return HealthStatus(
                    timestamp=datetime.now().isoformat(),
                    component=f'docker_{container_name}',
                    status='not_found',
                    details={},
                    error=f'Container {container_name} not found',
                    suggestions=[
                        'Start Docker Compose services',
                        f'Check if {container_name} is defined in docker-compose.yml'
                    ]
                )
            
            # Get container stats
            stats = {
                'status': container.status,
                'created': container.attrs['Created'],
                'started_at': container.attrs['State'].get('StartedAt'),
                'health_status': container.attrs['State'].get('Health', {}).get('Status'),
                'restart_count': container.attrs['RestartCount'],
                'ports': container.ports,
                'networks': list(container.attrs['NetworkSettings']['Networks'].keys())
            }
            
            # Check resource usage
            try:
                resource_stats = container.stats(stream=False)
                memory_usage = resource_stats['memory_stats']['usage'] / (1024**3)  # GB
                cpu_percent = self._calculate_cpu_percent(resource_stats)
                
                stats.update({
                    'memory_usage_gb': round(memory_usage, 2),
                    'cpu_percent': round(cpu_percent, 2)
                })
            except Exception as e:
                logger.warning(f"Could not get resource stats for {container_name}: {e}")
            
            # Determine overall status
            if container.status == 'running':
                health_status = container.attrs['State'].get('Health', {}).get('Status')
                if health_status == 'healthy' or health_status is None:
                    status = 'healthy'
                    suggestions = []
                else:
                    status = 'unhealthy'
                    suggestions = ['Check container logs', 'Restart container if needed']
            else:
                status = 'stopped'
                suggestions = [f'Start {container_name} container', 'Check Docker Compose configuration']
            
            return HealthStatus(
                timestamp=datetime.now().isoformat(),
                component=f'docker_{container_name}',
                status=status,
                details=stats,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Error checking container {container_name}: {e}")
            return HealthStatus(
                timestamp=datetime.now().isoformat(),
                component=f'docker_{container_name}',
                status='error',
                details={},
                error=str(e),
                suggestions=['Check Docker daemon status', 'Verify container configuration']
            )
    
    def _calculate_cpu_percent(self, stats: Dict) -> float:
        """Calculate CPU percentage from Docker stats"""
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * \
                             len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
                return cpu_percent
        except (KeyError, ZeroDivisionError):
            pass
        return 0.0
    
    def test_network_connectivity(self) -> HealthStatus:
        """Test network connectivity between containers"""
        try:
            connectivity_tests = []
            
            # Test PostgreSQL port connectivity
            pg_test = self._test_port_connectivity(
                self.config['db_host'], 
                self.config['db_port'], 
                'PostgreSQL'
            )
            connectivity_tests.append(pg_test)
            
            # Test Redis connectivity if configured
            if 'redis' in self.config:
                redis_test = self._test_port_connectivity(
                    self.config.get('redis_host', 'localhost'),
                    int(self.config.get('redis_port', 6379)),
                    'Redis'
                )
                connectivity_tests.append(redis_test)
            
            # Test Docker network connectivity
            if self.docker_client:
                network_test = self._test_docker_network()
                connectivity_tests.append(network_test)
            
            # Aggregate results
            failed_tests = [test for test in connectivity_tests if not test['success']]
            
            if not failed_tests:
                status = 'healthy'
                suggestions = []
            else:
                status = 'unhealthy'
                suggestions = [
                    'Check Docker network configuration',
                    'Verify container DNS resolution',
                    'Ensure all services are running'
                ]
            
            return HealthStatus(
                timestamp=datetime.now().isoformat(),
                component='network_connectivity',
                status=status,
                details={'tests': connectivity_tests, 'failed_count': len(failed_tests)},
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Network connectivity test failed: {e}")
            return HealthStatus(
                timestamp=datetime.now().isoformat(),
                component='network_connectivity',
                status='error',
                details={},
                error=str(e),
                suggestions=['Check network configuration', 'Verify Docker networking']
            )
    
    def _test_port_connectivity(self, host: str, port: int, service_name: str) -> Dict:
        """Test connectivity to a specific port"""
        import socket
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config['connection_timeout'])
            result = sock.connect_ex((host, port))
            sock.close()
            
            success = result == 0
            return {
                'service': service_name,
                'host': host,
                'port': port,
                'success': success,
                'error': None if success else f'Connection refused to {host}:{port}'
            }
        except Exception as e:
            return {
                'service': service_name,
                'host': host,
                'port': port,
                'success': False,
                'error': str(e)
            }
    
    def _test_docker_network(self) -> Dict:
        """Test Docker network connectivity"""
        try:
            # Get network information
            network_name = self.config['network_name']
            networks = self.docker_client.networks.list(names=[network_name])
            
            if not networks:
                return {
                    'service': 'Docker Network',
                    'network': network_name,
                    'success': False,
                    'error': f'Network {network_name} not found'
                }
            
            network = networks[0]
            containers = network.attrs['Containers']
            
            return {
                'service': 'Docker Network',
                'network': network_name,
                'success': True,
                'containers': len(containers),
                'container_names': [info['Name'] for info in containers.values()]
            }
            
        except Exception as e:
            return {
                'service': 'Docker Network',
                'success': False,
                'error': str(e)
            }
    
    def test_database_connection(self) -> HealthStatus:
        """Test direct database connection with detailed diagnostics"""
        try:
            # Test raw psycopg2 connection
            raw_connection_test = self._test_raw_connection()
            
            # Test SQLAlchemy connection if available
            sqlalchemy_test = self._test_sqlalchemy_connection()
            
            # Test connection pool if available
            pool_test = self._test_connection_pool()
            
            tests = {
                'raw_psycopg2': raw_connection_test,
                'sqlalchemy': sqlalchemy_test,
                'connection_pool': pool_test
            }
            
            # Determine overall status
            successful_tests = sum(1 for test in tests.values() if test and test.get('success', False))
            
            if successful_tests >= 2:  # At least 2 connection methods work
                status = 'healthy'
                suggestions = []
            elif successful_tests == 1:
                status = 'degraded'
                suggestions = ['Some connection methods failing', 'Check database configuration']
            else:
                status = 'unhealthy'
                suggestions = [
                    'Database connection completely failed',
                    'Check PostgreSQL container status',
                    'Verify database credentials',
                    'Check network connectivity'
                ]
            
            return HealthStatus(
                timestamp=datetime.now().isoformat(),
                component='database_connection',
                status=status,
                details=tests,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return HealthStatus(
                timestamp=datetime.now().isoformat(),
                component='database_connection',
                status='error',
                details={},
                error=str(e),
                suggestions=['Check database service status', 'Verify connection parameters']
            )
    
    def _test_raw_connection(self) -> Dict:
        """Test raw psycopg2 connection"""
        try:
            conn_params = {
                'host': self.config['db_host'],
                'port': self.config['db_port'],
                'database': self.config['db_name'],
                'user': self.config['db_user'],
                'password': self.config['db_password'],
                'connect_timeout': self.config['connection_timeout']
            }
            
            start_time = time.time()
            conn = psycopg2.connect(**conn_params)
            
            # Test basic query
            cur = conn.cursor()
            cur.execute('SELECT version(), current_database(), current_user;')
            version, database, user = cur.fetchone()
            
            # Get connection info
            conn_info = {
                'success': True,
                'connection_time_ms': round((time.time() - start_time) * 1000, 2),
                'postgres_version': version,
                'database': database,
                'user': user,
                'server_encoding': conn.encoding,
                'autocommit': conn.autocommit
            }
            
            cur.close()
            conn.close()
            
            return conn_info
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'connection_time_ms': None
            }
    
    def _test_sqlalchemy_connection(self) -> Optional[Dict]:
        """Test SQLAlchemy connection"""
        if not engine:
            return None
            
        try:
            start_time = time.time()
            
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version(), current_database();"))
                version, database = result.fetchone()
                
                # Get pool info if available
                pool_info = {}
                if hasattr(engine, 'pool') and engine.pool:
                    pool_info = {
                        'pool_size': engine.pool.size(),
                        'checked_out': engine.pool.checkedout(),
                        'overflow': engine.pool.overflow(),
                        'checked_in': engine.pool.checkedin()
                    }
                
                return {
                    'success': True,
                    'connection_time_ms': round((time.time() - start_time) * 1000, 2),
                    'postgres_version': version,
                    'database': database,
                    'pool_info': pool_info
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'connection_time_ms': None
            }
    
    def _test_connection_pool(self) -> Optional[Dict]:
        """Test connection pool performance"""
        if not engine or not hasattr(engine, 'pool'):
            return None
            
        try:
            # Test multiple concurrent connections
            start_time = time.time()
            connection_times = []
            
            def test_connection():
                conn_start = time.time()
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1;"))
                return time.time() - conn_start
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(test_connection) for _ in range(10)]
                
                for future in as_completed(futures):
                    try:
                        conn_time = future.result()
                        connection_times.append(conn_time)
                    except Exception as e:
                        logger.warning(f"Pool connection test failed: {e}")
            
            if connection_times:
                avg_time = sum(connection_times) / len(connection_times)
                max_time = max(connection_times)
                min_time = min(connection_times)
                
                return {
                    'success': True,
                    'total_test_time_ms': round((time.time() - start_time) * 1000, 2),
                    'connections_tested': len(connection_times),
                    'avg_connection_time_ms': round(avg_time * 1000, 2),
                    'max_connection_time_ms': round(max_time * 1000, 2),
                    'min_connection_time_ms': round(min_time * 1000, 2)
                }
            else:
                return {
                    'success': False,
                    'error': 'No successful connections in pool test'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_database_schema(self) -> HealthStatus:
        """Validate database initialization and schema"""
        try:
            if not engine:
                return HealthStatus(
                    timestamp=datetime.now().isoformat(),
                    component='database_schema',
                    status='error',
                    details={},
                    error='SQLAlchemy engine not available',
                    suggestions=['Check database configuration']
                )
            
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            expected_tables = self.config['expected_tables']
            
            # Check which tables exist
            missing_tables = [table for table in expected_tables if table not in existing_tables]
            extra_tables = [table for table in existing_tables if table not in expected_tables]
            
            # Get detailed table information
            table_details = {}
            for table in existing_tables:
                try:
                    columns = inspector.get_columns(table)
                    indexes = inspector.get_indexes(table)
                    foreign_keys = inspector.get_foreign_keys(table)
                    
                    table_details[table] = {
                        'columns': len(columns),
                        'indexes': len(indexes),
                        'foreign_keys': len(foreign_keys),
                        'column_names': [col['name'] for col in columns]
                    }
                except Exception as e:
                    table_details[table] = {'error': str(e)}
            
            # Determine status
            if not missing_tables:
                status = 'healthy'
                suggestions = []
            elif len(missing_tables) <= 2:  # Minor missing tables
                status = 'degraded'
                suggestions = ['Some tables missing', 'Run database migration']
            else:
                status = 'unhealthy'
                suggestions = [
                    'Multiple tables missing',
                    'Database not properly initialized',
                    'Run full database setup'
                ]
            
            return HealthStatus(
                timestamp=datetime.now().isoformat(),
                component='database_schema',
                status=status,
                details={
                    'existing_tables': existing_tables,
                    'expected_tables': expected_tables,
                    'missing_tables': missing_tables,
                    'extra_tables': extra_tables,
                    'table_details': table_details,
                    'total_tables': len(existing_tables)
                },
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return HealthStatus(
                timestamp=datetime.now().isoformat(),
                component='database_schema',
                status='error',
                details={},
                error=str(e),
                suggestions=['Check database connectivity', 'Verify schema setup']
            )
    
    def run_comprehensive_health_check(self) -> Dict[str, HealthStatus]:
        """Run all health checks in parallel"""
        logger.info("Starting comprehensive health check...")
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Submit all health check tasks
            futures = {
                'postgres_container': executor.submit(self.check_docker_container_health, 'postgres'),
                'backend_container': executor.submit(self.check_docker_container_health, 'backend'), 
                'redis_container': executor.submit(self.check_docker_container_health, 'redis'),
                'network_connectivity': executor.submit(self.test_network_connectivity),
                'database_connection': executor.submit(self.test_database_connection),
                'database_schema': executor.submit(self.validate_database_schema)
            }
            
            # Collect results
            for component, future in futures.items():
                try:
                    results[component] = future.result(timeout=30)
                except Exception as e:
                    logger.error(f"Health check failed for {component}: {e}")
                    results[component] = HealthStatus(
                        timestamp=datetime.now().isoformat(),
                        component=component,
                        status='error',
                        details={},
                        error=str(e)
                    )
        
        # Store results in history
        self.health_history.append({
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        # Keep only last 100 records
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
        
        return results
    
    def get_health_summary(self, results: Dict[str, HealthStatus]) -> Dict:
        """Generate health summary with recommendations"""
        healthy_components = sum(1 for result in results.values() if result.status == 'healthy')
        total_components = len(results)
        
        # Categorize issues
        critical_issues = [comp for comp, result in results.items() if result.status == 'error']
        warnings = [comp for comp, result in results.items() if result.status in ['degraded', 'unhealthy']]
        
        # Generate recommendations
        recommendations = []
        for component, result in results.items():
            if result.suggestions:
                recommendations.extend([f"{component}: {suggestion}" for suggestion in result.suggestions])
        
        # Overall system status
        if healthy_components == total_components:
            overall_status = 'healthy'
        elif healthy_components >= total_components * 0.7:  # 70% healthy
            overall_status = 'degraded'
        elif critical_issues:
            overall_status = 'critical'
        else:
            overall_status = 'unhealthy'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'health_score': round((healthy_components / total_components) * 100, 1),
            'components': {
                'total': total_components,
                'healthy': healthy_components,
                'critical_issues': len(critical_issues),
                'warnings': len(warnings)
            },
            'critical_issues': critical_issues,
            'warnings': warnings,
            'recommendations': recommendations[:10],  # Top 10 recommendations
            'detailed_results': {comp: asdict(result) for comp, result in results.items()}
        }
    
    def start_continuous_monitoring(self, interval: int = None) -> None:
        """Start continuous health monitoring"""
        if self.monitoring:
            logger.warning("Monitoring already running")
            return
            
        interval = interval or self.config['health_check_interval']
        self.monitoring = True
        
        def monitor_loop():
            logger.info(f"Starting continuous monitoring (interval: {interval}s)")
            
            while self.monitoring:
                try:
                    results = self.run_comprehensive_health_check()
                    summary = self.get_health_summary(results)
                    
                    # Log status
                    logger.info(f"Health Check - Status: {summary['overall_status']}, "
                              f"Score: {summary['health_score']}%")
                    
                    # Check for alerts
                    if summary['overall_status'] in ['critical', 'unhealthy']:
                        alert = {
                            'timestamp': datetime.now().isoformat(),
                            'severity': summary['overall_status'],
                            'message': f"System health degraded: {summary['health_score']}% healthy",
                            'details': summary
                        }
                        self.alerts.append(alert)
                        logger.warning(f"ALERT: {alert['message']}")
                    
                    # Save health report
                    self._save_health_report(summary)
                    
                except Exception as e:
                    logger.error(f"Monitoring iteration failed: {e}")
                
                # Wait for next iteration
                for _ in range(interval):
                    if not self.monitoring:
                        break
                    time.sleep(1)
            
            logger.info("Continuous monitoring stopped")
        
        # Start monitoring in background thread
        monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitoring_thread.start()
    
    def stop_continuous_monitoring(self) -> None:
        """Stop continuous health monitoring"""
        self.monitoring = False
        logger.info("Stopping continuous monitoring...")
    
    def _save_health_report(self, summary: Dict) -> None:
        """Save health report to file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = f'/home/user/Testing/ai-model-validation-platform/backend/logs/health_report_{timestamp}.json'
            
            with open(report_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
                
        except Exception as e:
            logger.warning(f"Could not save health report: {e}")
    
    def generate_troubleshooting_guide(self, results: Dict[str, HealthStatus]) -> str:
        """Generate troubleshooting guide based on health check results"""
        guide = []
        guide.append("# PostgreSQL Health Check Troubleshooting Guide")
        guide.append(f"Generated: {datetime.now().isoformat()}\n")
        
        # Overall status
        summary = self.get_health_summary(results)
        guide.append(f"## Overall System Status: {summary['overall_status'].upper()}")
        guide.append(f"Health Score: {summary['health_score']}%\n")
        
        # Critical issues
        if summary['critical_issues']:
            guide.append("## 🚨 CRITICAL ISSUES")
            for component in summary['critical_issues']:
                result = results[component]
                guide.append(f"\n### {component}")
                guide.append(f"- Status: {result.status}")
                guide.append(f"- Error: {result.error}")
                if result.suggestions:
                    guide.append("- Suggested Actions:")
                    for suggestion in result.suggestions:
                        guide.append(f"  - {suggestion}")
        
        # Warnings
        if summary['warnings']:
            guide.append("\n## ⚠️ WARNINGS")
            for component in summary['warnings']:
                result = results[component]
                guide.append(f"\n### {component}")
                guide.append(f"- Status: {result.status}")
                if result.suggestions:
                    guide.append("- Suggested Actions:")
                    for suggestion in result.suggestions:
                        guide.append(f"  - {suggestion}")
        
        # Quick recovery commands
        guide.append("\n## 🛠️ QUICK RECOVERY COMMANDS")
        guide.append("```bash")
        guide.append("# Restart all containers")
        guide.append("cd /home/user/Testing/ai-model-validation-platform")
        guide.append("docker-compose down && docker-compose up -d")
        guide.append("")
        guide.append("# Check container logs")
        guide.append("docker-compose logs postgres")
        guide.append("docker-compose logs backend")
        guide.append("")
        guide.append("# Recreate database")
        guide.append("docker-compose exec postgres psql -U postgres -c 'DROP DATABASE IF EXISTS vru_validation;'")
        guide.append("docker-compose exec postgres psql -U postgres -c 'CREATE DATABASE vru_validation;'")
        guide.append("docker-compose exec backend python database_init.py")
        guide.append("```")
        
        return "\n".join(guide)

def main():
    """Main health check execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PostgreSQL Health Check Tool')
    parser.add_argument('--monitor', action='store_true', help='Start continuous monitoring')
    parser.add_argument('--interval', type=int, default=30, help='Monitoring interval in seconds')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--troubleshoot', action='store_true', help='Generate troubleshooting guide')
    
    args = parser.parse_args()
    
    # Create health checker
    checker = PostgreSQLHealthChecker()
    
    if args.monitor:
        # Start continuous monitoring
        try:
            checker.start_continuous_monitoring(args.interval)
            
            # Keep running until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping monitoring...")
            checker.stop_continuous_monitoring()
    else:
        # Run single health check
        results = checker.run_comprehensive_health_check()
        summary = checker.get_health_summary(results)
        
        # Display results
        print(f"\n=== PostgreSQL Health Check Results ===")
        print(f"Overall Status: {summary['overall_status'].upper()}")
        print(f"Health Score: {summary['health_score']}%")
        print(f"Components: {summary['components']['healthy']}/{summary['components']['total']} healthy")
        
        if summary['critical_issues']:
            print(f"\n🚨 Critical Issues: {', '.join(summary['critical_issues'])}")
        
        if summary['warnings']:
            print(f"\n⚠️  Warnings: {', '.join(summary['warnings'])}")
        
        if summary['recommendations']:
            print(f"\n💡 Top Recommendations:")
            for rec in summary['recommendations'][:5]:
                print(f"  - {rec}")
        
        # Save results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            print(f"\nResults saved to: {args.output}")
        
        # Generate troubleshooting guide if requested
        if args.troubleshoot:
            guide = checker.generate_troubleshooting_guide(results)
            guide_file = '/home/user/Testing/ai-model-validation-platform/backend/logs/troubleshooting_guide.md'
            with open(guide_file, 'w') as f:
                f.write(guide)
            print(f"\nTroubleshooting guide saved to: {guide_file}")
            print("\n" + guide)

if __name__ == '__main__':
    main()
