#!/usr/bin/env python3
"""
Database Connection Validator for AI Model Validation Platform

Comprehensive validation of database connectivity from backend container
to PostgreSQL with detailed connection testing, pool monitoring, and
recovery mechanisms.

Features:
- Backend-to-PostgreSQL connection validation
- SQLAlchemy connection pool monitoring
- Transaction testing and rollback verification
- Connection recovery and retry mechanisms
- Performance benchmarking
- Concurrent connection testing
"""

import os
import sys
import time
import json
import logging
import threading
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add backend directory to path
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from sqlalchemy import create_engine, text, inspect, MetaData
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import QueuePool
    from sqlalchemy.exc import SQLAlchemyError, OperationalError, DisconnectionError
    
    # Import application modules
    from database import get_db, get_database_health, engine, DATABASE_URL, SessionLocal
    from models import Base, Project, Video, GroundTruthObject, TestSession
except ImportError as e:
    print(f"Warning: Some database modules unavailable: {e}")
    engine = None
    DATABASE_URL = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ConnectionTestResult:
    """Connection test result structure"""
    test_name: str
    success: bool
    duration_ms: float
    details: Dict[str, Any]
    error: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

class DatabaseConnectionValidator:
    """Comprehensive database connection validation system"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._load_config()
        self.test_results = []
        self.connection_stats = {
            'total_tests': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'avg_connection_time': 0,
            'connection_errors': []
        }
        
    def _load_config(self) -> Dict:
        """Load configuration from environment"""
        return {
            'db_host': os.getenv('DATABASE_HOST', 'postgres'),
            'db_port': int(os.getenv('DATABASE_PORT', '5432')),
            'db_name': os.getenv('POSTGRES_DB', 'vru_validation'),
            'db_user': os.getenv('POSTGRES_USER', 'postgres'),
            'db_password': os.getenv('POSTGRES_PASSWORD', 'secure_password_change_me'),
            'connection_timeout': 30,
            'retry_attempts': 5,
            'retry_delay': 2,
            'pool_size': 10,
            'max_overflow': 20,
            'concurrent_connections': 10,
            'stress_test_duration': 60,
            'expected_tables': [
                'projects', 'videos', 'ground_truth_objects', 'test_sessions',
                'detection_events', 'annotations', 'annotation_sessions',
                'validation_results', 'model_versions', 'video_project_links',
                'system_config'
            ]
        }
    
    def test_raw_psycopg2_connection(self) -> ConnectionTestResult:
        """Test raw psycopg2 connection to PostgreSQL"""
        start_time = time.time()
        
        try:
            conn_params = {
                'host': self.config['db_host'],
                'port': self.config['db_port'],
                'database': self.config['db_name'],
                'user': self.config['db_user'],
                'password': self.config['db_password'],
                'connect_timeout': self.config['connection_timeout']
            }
            
            # Test connection with retry logic
            last_error = None
            for attempt in range(self.config['retry_attempts']):
                try:
                    conn = psycopg2.connect(**conn_params)
                    
                    # Test basic query
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT 
                                version() as postgres_version,
                                current_database() as database_name,
                                current_user as user_name,
                                inet_server_addr() as server_ip,
                                inet_server_port() as server_port,
                                current_timestamp as connection_time,
                                pg_backend_pid() as backend_pid
                        """)
                        result = cur.fetchone()
                        
                        # Test transaction capabilities
                        cur.execute("BEGIN;")
                        cur.execute("SELECT 1 as transaction_test;")
                        cur.execute("ROLLBACK;")
                        
                        # Get database size and connection info
                        cur.execute("""
                            SELECT 
                                pg_size_pretty(pg_database_size(current_database())) as db_size,
                                count(*) as active_connections
                            FROM pg_stat_activity 
                            WHERE datname = current_database()
                        """)
                        size_info = cur.fetchone()
                    
                    conn.close()
                    
                    duration = (time.time() - start_time) * 1000
                    
                    return ConnectionTestResult(
                        test_name='raw_psycopg2_connection',
                        success=True,
                        duration_ms=round(duration, 2),
                        details={
                            'connection_attempt': attempt + 1,
                            'postgres_version': result['postgres_version'],
                            'database_name': result['database_name'],
                            'user_name': result['user_name'],
                            'server_ip': result['server_ip'],
                            'server_port': result['server_port'],
                            'connection_time': str(result['connection_time']),
                            'backend_pid': result['backend_pid'],
                            'database_size': size_info['db_size'],
                            'active_connections': size_info['active_connections'],
                            'transaction_support': True
                        }
                    )
                    
                except (psycopg2.OperationalError, psycopg2.DatabaseError) as e:
                    last_error = str(e)
                    if attempt < self.config['retry_attempts'] - 1:
                        logger.warning(f"Connection attempt {attempt + 1} failed: {e}. Retrying...")
                        time.sleep(self.config['retry_delay'])
                    else:
                        logger.error(f"All connection attempts failed: {e}")
            
            # All attempts failed
            duration = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                test_name='raw_psycopg2_connection',
                success=False,
                duration_ms=round(duration, 2),
                details={'retry_attempts': self.config['retry_attempts']},
                error=last_error
            )
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                test_name='raw_psycopg2_connection',
                success=False,
                duration_ms=round(duration, 2),
                details={},
                error=str(e)
            )
    
    def test_sqlalchemy_connection(self) -> ConnectionTestResult:
        """Test SQLAlchemy connection and ORM functionality"""
        start_time = time.time()
        
        try:
            if not engine:
                return ConnectionTestResult(
                    test_name='sqlalchemy_connection',
                    success=False,
                    duration_ms=0,
                    details={},
                    error='SQLAlchemy engine not available'
                )
            
            # Test basic connection
            with engine.connect() as conn:
                # Basic connectivity test
                result = conn.execute(text("""
                    SELECT 
                        version() as postgres_version,
                        current_database() as database_name,
                        current_timestamp as connection_time
                """))
                basic_info = result.fetchone()
                
                # Test transaction handling
                trans = conn.begin()
                conn.execute(text("SELECT 1 as transaction_test"))
                trans.rollback()
                
                # Get connection pool information
                pool_info = {}
                if hasattr(engine, 'pool') and engine.pool:
                    pool_info = {
                        'pool_size': engine.pool.size(),
                        'checked_out': engine.pool.checkedout(),
                        'overflow': engine.pool.overflow(),
                        'checked_in': engine.pool.checkedin(),
                        'pool_class': str(type(engine.pool).__name__)
                    }
                
                duration = (time.time() - start_time) * 1000
                
                return ConnectionTestResult(
                    test_name='sqlalchemy_connection',
                    success=True,
                    duration_ms=round(duration, 2),
                    details={
                        'postgres_version': basic_info[0],
                        'database_name': basic_info[1],
                        'connection_time': str(basic_info[2]),
                        'pool_info': pool_info,
                        'engine_url': str(engine.url).replace(engine.url.password, '***'),
                        'transaction_support': True
                    }
                )
                
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                test_name='sqlalchemy_connection',
                success=False,
                duration_ms=round(duration, 2),
                details={},
                error=str(e)
            )
    
    def test_orm_functionality(self) -> ConnectionTestResult:
        """Test SQLAlchemy ORM functionality and model operations"""
        start_time = time.time()
        
        try:
            db = SessionLocal()
            
            try:
                # Test basic ORM query capabilities
                projects_count = db.query(Project).count()
                videos_count = db.query(Video).count()
                
                # Test model relationships (if data exists)
                relationship_test = db.query(Project).join(Video, isouter=True).count()
                
                # Test complex query
                complex_query = db.query(Video).filter(
                    Video.status == 'uploaded'
                ).limit(5).all()
                
                # Test transaction capabilities
                db.begin()
                test_project = Project(
                    name='Test Connection Project',
                    camera_model='Test Camera',
                    camera_view='Test View',
                    signal_type='Test Signal'
                )
                db.add(test_project)
                db.flush()  # Get ID without committing
                test_project_id = test_project.id
                db.rollback()  # Rollback test transaction
                
                duration = (time.time() - start_time) * 1000
                
                return ConnectionTestResult(
                    test_name='orm_functionality',
                    success=True,
                    duration_ms=round(duration, 2),
                    details={
                        'projects_count': projects_count,
                        'videos_count': videos_count,
                        'relationship_queries': relationship_test,
                        'complex_query_results': len(complex_query),
                        'transaction_test_id': test_project_id,
                        'orm_models_accessible': True
                    }
                )
                
            finally:
                db.close()
                
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                test_name='orm_functionality',
                success=False,
                duration_ms=round(duration, 2),
                details={},
                error=str(e)
            )
    
    def test_connection_pool_performance(self) -> ConnectionTestResult:
        """Test connection pool performance under load"""
        start_time = time.time()
        
        try:
            if not engine or not hasattr(engine, 'pool'):
                return ConnectionTestResult(
                    test_name='connection_pool_performance',
                    success=False,
                    duration_ms=0,
                    details={},
                    error='Connection pool not available'
                )
            
            connection_times = []
            successful_connections = 0
            failed_connections = 0
            
            def test_single_connection():
                """Test a single connection from the pool"""
                conn_start = time.time()
                try:
                    with engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                        return time.time() - conn_start
                except Exception as e:
                    logger.warning(f"Pool connection failed: {e}")
                    return None
            
            # Test concurrent connections
            with ThreadPoolExecutor(max_workers=self.config['concurrent_connections']) as executor:
                futures = [executor.submit(test_single_connection) for _ in range(20)]
                
                for future in as_completed(futures):
                    result = future.result()
                    if result is not None:
                        connection_times.append(result)
                        successful_connections += 1
                    else:
                        failed_connections += 1
            
            # Calculate statistics
            if connection_times:
                avg_time = sum(connection_times) / len(connection_times)
                min_time = min(connection_times)
                max_time = max(connection_times)
                
                # Get pool statistics after test
                pool_stats = {
                    'pool_size': engine.pool.size(),
                    'checked_out': engine.pool.checkedout(),
                    'overflow': engine.pool.overflow(),
                    'checked_in': engine.pool.checkedin()
                }
                
                duration = (time.time() - start_time) * 1000
                
                return ConnectionTestResult(
                    test_name='connection_pool_performance',
                    success=successful_connections > 0,
                    duration_ms=round(duration, 2),
                    details={
                        'successful_connections': successful_connections,
                        'failed_connections': failed_connections,
                        'avg_connection_time_ms': round(avg_time * 1000, 2),
                        'min_connection_time_ms': round(min_time * 1000, 2),
                        'max_connection_time_ms': round(max_time * 1000, 2),
                        'pool_stats': pool_stats,
                        'concurrent_connections_tested': len(connection_times)
                    }
                )
            else:
                duration = (time.time() - start_time) * 1000
                return ConnectionTestResult(
                    test_name='connection_pool_performance',
                    success=False,
                    duration_ms=round(duration, 2),
                    details={'failed_connections': failed_connections},
                    error='No successful connections in pool test'
                )
                
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                test_name='connection_pool_performance',
                success=False,
                duration_ms=round(duration, 2),
                details={},
                error=str(e)
            )
    
    def test_database_schema_integrity(self) -> ConnectionTestResult:
        """Test database schema integrity and table structure"""
        start_time = time.time()
        
        try:
            if not engine:
                return ConnectionTestResult(
                    test_name='database_schema_integrity',
                    success=False,
                    duration_ms=0,
                    details={},
                    error='SQLAlchemy engine not available'
                )
            
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            expected_tables = self.config['expected_tables']
            
            # Check table existence
            missing_tables = [table for table in expected_tables if table not in existing_tables]
            extra_tables = [table for table in existing_tables if table not in expected_tables]
            
            # Detailed table analysis
            table_analysis = {}
            for table_name in existing_tables:
                try:
                    columns = inspector.get_columns(table_name)
                    indexes = inspector.get_indexes(table_name)
                    foreign_keys = inspector.get_foreign_keys(table_name)
                    primary_keys = inspector.get_pk_constraint(table_name)
                    
                    # Get table statistics
                    with engine.connect() as conn:
                        result = conn.execute(text(f"""
                            SELECT 
                                reltuples::bigint as row_count,
                                pg_size_pretty(pg_total_relation_size('{table_name}')) as table_size
                            FROM pg_class 
                            WHERE relname = '{table_name}'
                        """))
                        stats = result.fetchone()
                    
                    table_analysis[table_name] = {
                        'columns': len(columns),
                        'indexes': len(indexes),
                        'foreign_keys': len(foreign_keys),
                        'primary_keys': len(primary_keys.get('constrained_columns', [])),
                        'estimated_rows': stats[0] if stats else 0,
                        'table_size': stats[1] if stats else 'unknown',
                        'column_names': [col['name'] for col in columns],
                        'index_names': [idx['name'] for idx in indexes]
                    }
                    
                except Exception as e:
                    table_analysis[table_name] = {'error': str(e)}
            
            # Test critical relationships
            relationship_tests = {}
            try:
                with engine.connect() as conn:
                    # Test foreign key relationships
                    fk_result = conn.execute(text("""
                        SELECT 
                            COUNT(*) as total_foreign_keys
                        FROM information_schema.table_constraints 
                        WHERE constraint_type = 'FOREIGN KEY'
                    """))
                    relationship_tests['total_foreign_keys'] = fk_result.fetchone()[0]
                    
                    # Test referential integrity (sample)
                    if 'videos' in existing_tables and 'projects' in existing_tables:
                        integrity_result = conn.execute(text("""
                            SELECT COUNT(*) as orphaned_videos
                            FROM videos v
                            LEFT JOIN projects p ON v.project_id = p.id
                            WHERE p.id IS NULL
                        """))
                        relationship_tests['orphaned_videos'] = integrity_result.fetchone()[0]
                        
            except Exception as e:
                relationship_tests['error'] = str(e)
            
            duration = (time.time() - start_time) * 1000
            
            # Determine success based on missing critical tables
            critical_tables = ['projects', 'videos', 'ground_truth_objects']
            missing_critical = [table for table in critical_tables if table in missing_tables]
            
            success = len(missing_critical) == 0
            
            return ConnectionTestResult(
                test_name='database_schema_integrity',
                success=success,
                duration_ms=round(duration, 2),
                details={
                    'existing_tables': existing_tables,
                    'expected_tables': expected_tables,
                    'missing_tables': missing_tables,
                    'extra_tables': extra_tables,
                    'missing_critical_tables': missing_critical,
                    'total_tables': len(existing_tables),
                    'table_analysis': table_analysis,
                    'relationship_tests': relationship_tests
                },
                error=f"Missing critical tables: {missing_critical}" if missing_critical else None
            )
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                test_name='database_schema_integrity',
                success=False,
                duration_ms=round(duration, 2),
                details={},
                error=str(e)
            )
    
    def test_connection_recovery(self) -> ConnectionTestResult:
        """Test connection recovery mechanisms"""
        start_time = time.time()
        
        try:
            if not engine:
                return ConnectionTestResult(
                    test_name='connection_recovery',
                    success=False,
                    duration_ms=0,
                    details={},
                    error='SQLAlchemy engine not available'
                )
            
            recovery_attempts = []
            
            # Test 1: Connection after pool exhaustion
            try:
                connections = []
                # Exhaust the connection pool
                for i in range(engine.pool.size() + engine.pool.overflow() + 1):
                    try:
                        conn = engine.connect()
                        connections.append(conn)
                    except Exception:
                        break
                
                # Try to get another connection (should fail or wait)
                recovery_start = time.time()
                try:
                    test_conn = engine.connect()
                    test_conn.execute(text("SELECT 1"))
                    test_conn.close()
                    recovery_time = (time.time() - recovery_start) * 1000
                    recovery_attempts.append({
                        'test': 'pool_exhaustion_recovery',
                        'success': True,
                        'recovery_time_ms': round(recovery_time, 2)
                    })
                except Exception as e:
                    recovery_attempts.append({
                        'test': 'pool_exhaustion_recovery',
                        'success': False,
                        'error': str(e)
                    })
                finally:
                    # Clean up connections
                    for conn in connections:
                        try:
                            conn.close()
                        except:
                            pass
                            
            except Exception as e:
                recovery_attempts.append({
                    'test': 'pool_exhaustion_recovery',
                    'success': False,
                    'error': str(e)
                })
            
            # Test 2: Reconnection after brief disconnection simulation
            try:
                # Test normal connection
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                
                # Simulate brief wait and reconnect
                time.sleep(1)
                
                recovery_start = time.time()
                with engine.connect() as conn:
                    conn.execute(text("SELECT current_timestamp"))
                    recovery_time = (time.time() - recovery_start) * 1000
                    
                recovery_attempts.append({
                    'test': 'reconnection_after_wait',
                    'success': True,
                    'recovery_time_ms': round(recovery_time, 2)
                })
                
            except Exception as e:
                recovery_attempts.append({
                    'test': 'reconnection_after_wait',
                    'success': False,
                    'error': str(e)
                })
            
            # Test 3: Application-level retry logic
            try:
                retry_attempts = 0
                max_retries = 3
                
                for attempt in range(max_retries):
                    try:
                        recovery_start = time.time()
                        with engine.connect() as conn:
                            conn.execute(text("SELECT 1"))
                        recovery_time = (time.time() - recovery_start) * 1000
                        
                        recovery_attempts.append({
                            'test': 'application_retry_logic',
                            'success': True,
                            'retry_attempts': attempt,
                            'recovery_time_ms': round(recovery_time, 2)
                        })
                        break
                        
                    except Exception as e:
                        retry_attempts += 1
                        if attempt < max_retries - 1:
                            time.sleep(self.config['retry_delay'])
                        else:
                            recovery_attempts.append({
                                'test': 'application_retry_logic',
                                'success': False,
                                'retry_attempts': retry_attempts,
                                'error': str(e)
                            })
                            
            except Exception as e:
                recovery_attempts.append({
                    'test': 'application_retry_logic',
                    'success': False,
                    'error': str(e)
                })
            
            duration = (time.time() - start_time) * 1000
            successful_recoveries = sum(1 for attempt in recovery_attempts if attempt.get('success', False))
            
            return ConnectionTestResult(
                test_name='connection_recovery',
                success=successful_recoveries > 0,
                duration_ms=round(duration, 2),
                details={
                    'recovery_attempts': recovery_attempts,
                    'successful_recoveries': successful_recoveries,
                    'total_recovery_tests': len(recovery_attempts)
                }
            )
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ConnectionTestResult(
                test_name='connection_recovery',
                success=False,
                duration_ms=round(duration, 2),
                details={},
                error=str(e)
            )
    
    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive database connection validation"""
        logger.info("Starting comprehensive database connection validation...")
        
        test_results = []
        
        # Define tests to run
        tests = [
            self.test_raw_psycopg2_connection,
            self.test_sqlalchemy_connection,
            self.test_orm_functionality,
            self.test_connection_pool_performance,
            self.test_database_schema_integrity,
            self.test_connection_recovery
        ]
        
        # Run tests sequentially (some tests may affect others)
        for test_func in tests:
            try:
                logger.info(f"Running {test_func.__name__}...")
                result = test_func()
                test_results.append(result)
                
                # Update statistics
                self.connection_stats['total_tests'] += 1
                if result.success:
                    self.connection_stats['successful_connections'] += 1
                else:
                    self.connection_stats['failed_connections'] += 1
                    if result.error:
                        self.connection_stats['connection_errors'].append({
                            'test': result.test_name,
                            'error': result.error,
                            'timestamp': result.timestamp
                        })
                        
            except Exception as e:
                logger.error(f"Test {test_func.__name__} crashed: {e}")
                test_results.append(ConnectionTestResult(
                    test_name=test_func.__name__,
                    success=False,
                    duration_ms=0,
                    details={},
                    error=f"Test crashed: {str(e)}"
                ))
        
        # Calculate overall statistics
        successful_tests = sum(1 for result in test_results if result.success)
        total_tests = len(test_results)
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # Calculate average connection time for successful tests
        successful_durations = [r.duration_ms for r in test_results if r.success and r.duration_ms > 0]
        avg_duration = sum(successful_durations) / len(successful_durations) if successful_durations else 0
        
        # Generate recommendations
        recommendations = []
        
        if success_rate < 50:
            recommendations.append("Critical: Less than 50% of connection tests passed")
        elif success_rate < 80:
            recommendations.append("Warning: Some connection issues detected")
        
        if avg_duration > 1000:
            recommendations.append("High connection latency detected - check network or database performance")
        
        failed_tests = [r.test_name for r in test_results if not r.success]
        if failed_tests:
            recommendations.append(f"Failed tests require attention: {', '.join(failed_tests)}")
        
        # Check for specific issues
        schema_result = next((r for r in test_results if r.test_name == 'database_schema_integrity'), None)
        if schema_result and not schema_result.success:
            recommendations.append("Database schema issues detected - run database initialization")
        
        pool_result = next((r for r in test_results if r.test_name == 'connection_pool_performance'), None)
        if pool_result and pool_result.success:
            pool_details = pool_result.details
            if pool_details.get('failed_connections', 0) > 0:
                recommendations.append("Connection pool showing failures - consider tuning pool settings")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy' if success_rate >= 80 else 'degraded' if success_rate >= 50 else 'critical',
            'success_rate': round(success_rate, 1),
            'successful_tests': successful_tests,
            'total_tests': total_tests,
            'average_connection_time_ms': round(avg_duration, 2),
            'test_results': [asdict(result) for result in test_results],
            'connection_statistics': self.connection_stats,
            'recommendations': recommendations,
            'configuration': {
                'database_url': str(DATABASE_URL).replace(self.config['db_password'], '***') if DATABASE_URL else None,
                'connection_timeout': self.config['connection_timeout'],
                'retry_attempts': self.config['retry_attempts'],
                'pool_size': self.config['pool_size'],
                'max_overflow': self.config['max_overflow']
            }
        }
    
    def save_validation_results(self, results: Dict[str, Any], filename: str = None) -> str:
        """Save validation results to file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/home/user/Testing/ai-model-validation-platform/backend/logs/db_validation_{timestamp}.json'
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        return filename
    
    def generate_validation_report(self, results: Dict[str, Any]) -> str:
        """Generate human-readable validation report"""
        report = []
        report.append("# Database Connection Validation Report")
        report.append(f"Generated: {results['timestamp']}\n")
        
        # Overall status
        status_emoji = {
            'healthy': '✅',
            'degraded': '⚠️',
            'critical': '🚨'
        }
        
        report.append(f"## Overall Status: {status_emoji.get(results['overall_status'], '❓')} {results['overall_status'].upper()}")
        report.append(f"Success Rate: {results['success_rate']}% ({results['successful_tests']}/{results['total_tests']} tests)")
        report.append(f"Average Connection Time: {results['average_connection_time_ms']}ms\n")
        
        # Test results details
        report.append("## Test Results")
        for test_result in results['test_results']:
            status = "✅" if test_result['success'] else "❌"
            duration = f" ({test_result['duration_ms']}ms)" if test_result['duration_ms'] > 0 else ""
            
            report.append(f"### {status} {test_result['test_name']}{duration}")
            
            if test_result['success']:
                if test_result['details']:
                    key_details = {}
                    details = test_result['details']
                    
                    # Extract key information based on test type
                    if 'postgres_version' in details:
                        key_details['PostgreSQL Version'] = details['postgres_version'].split(' ')[0]
                    if 'database_name' in details:
                        key_details['Database'] = details['database_name']
                    if 'successful_connections' in details:
                        key_details['Successful Connections'] = details['successful_connections']
                    if 'total_tables' in details:
                        key_details['Tables Found'] = details['total_tables']
                    if 'pool_stats' in details and details['pool_stats']:
                        pool = details['pool_stats']
                        key_details['Pool Status'] = f"{pool.get('checked_out', 0)}/{pool.get('pool_size', 0)} active"
                    
                    for key, value in key_details.items():
                        report.append(f"  - {key}: {value}")
            else:
                report.append(f"  - Error: {test_result.get('error', 'Unknown error')}")
            
            report.append("")
        
        # Recommendations
        if results['recommendations']:
            report.append("## 💡 Recommendations")
            for rec in results['recommendations']:
                report.append(f"- {rec}")
            report.append("")
        
        # Configuration info
        config = results['configuration']
        if config:
            report.append("## Configuration")
            if config['database_url']:
                report.append(f"- Database URL: {config['database_url']}")
            report.append(f"- Connection Timeout: {config['connection_timeout']}s")
            report.append(f"- Retry Attempts: {config['retry_attempts']}")
            report.append(f"- Pool Size: {config['pool_size']} (max overflow: {config['max_overflow']})")
            report.append("")
        
        # Quick fix commands
        if results['overall_status'] != 'healthy':
            report.append("## 🔧 Quick Fix Commands")
            report.append("```bash")
            report.append("# Check PostgreSQL container")
            report.append("docker-compose logs postgres")
            report.append("")
            report.append("# Restart database services")
            report.append("cd /home/user/Testing/ai-model-validation-platform")
            report.append("docker-compose restart postgres")
            report.append("docker-compose restart backend")
            report.append("")
            report.append("# Recreate database if needed")
            report.append("docker-compose exec backend python database_init.py")
            report.append("```")
        
        return "\n".join(report)

def main():
    """Main validation execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Connection Validation Tool')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--report', action='store_true', help='Generate human-readable report')
    parser.add_argument('--test', choices=['psycopg2', 'sqlalchemy', 'orm', 'pool', 'schema', 'recovery'], 
                       help='Run specific test only')
    
    args = parser.parse_args()
    
    validator = DatabaseConnectionValidator()
    
    if args.test:
        # Run specific test
        test_methods = {
            'psycopg2': validator.test_raw_psycopg2_connection,
            'sqlalchemy': validator.test_sqlalchemy_connection,
            'orm': validator.test_orm_functionality,
            'pool': validator.test_connection_pool_performance,
            'schema': validator.test_database_schema_integrity,
            'recovery': validator.test_connection_recovery
        }
        
        test_method = test_methods[args.test]
        result = test_method()
        
        print(f"\n=== {result.test_name} Test ===")
        print(f"Status: {'✅ PASS' if result.success else '❌ FAIL'}")
        print(f"Duration: {result.duration_ms}ms")
        
        if result.error:
            print(f"Error: {result.error}")
        
        if result.details:
            print(f"\nDetails:")
            for key, value in result.details.items():
                print(f"  {key}: {value}")
    
    else:
        # Run comprehensive validation
        results = validator.run_comprehensive_validation()
        
        # Display summary
        print(f"\n=== Database Connection Validation Results ===")
        print(f"Overall Status: {results['overall_status'].upper()}")
        print(f"Success Rate: {results['success_rate']}%")
        print(f"Tests: {results['successful_tests']}/{results['total_tests']}")
        print(f"Average Connection Time: {results['average_connection_time_ms']}ms")
        
        if results['recommendations']:
            print(f"\n⚠️  Recommendations:")
            for rec in results['recommendations']:
                print(f"  - {rec}")
        
        # Save results
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'/home/user/Testing/ai-model-validation-platform/backend/logs/db_validation_{timestamp}.json'
        
        saved_file = validator.save_validation_results(results, output_file)
        print(f"\nResults saved to: {saved_file}")
        
        # Generate report if requested
        if args.report:
            report = validator.generate_validation_report(results)
            report_file = saved_file.replace('.json', '_report.md')
            with open(report_file, 'w') as f:
                f.write(report)
            print(f"Report saved to: {report_file}")
            print(f"\n{report}")

if __name__ == '__main__':
    main()
