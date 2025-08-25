#!/usr/bin/env python3
"""
Database Recovery Process Testing

Comprehensive testing of complete database recovery scenarios including
container restarts, connection restoration, and table recreation.

Features:
- Complete recovery scenario simulation
- Container failure and restart testing
- Connection restoration validation
- Database initialization after recovery
- Performance impact measurement
- Recovery time optimization
- Automated recovery verification
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

# Add backend directory to path
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')

try:
    from db_health_check import PostgreSQLHealthChecker
    from network_connectivity_test import NetworkConnectivityTester
    from database_connection_validator import DatabaseConnectionValidator
    from database_init_verifier import DatabaseInitializationVerifier
    from table_creation_tester import TableCreationTester
    from diagnostic_toolkit import DiagnosticToolkit, DiagnosticLevel
except ImportError as e:
    print(f"Warning: Some testing modules unavailable: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RecoveryScenario(Enum):
    """Recovery scenario types"""
    CONTAINER_RESTART = "container_restart"
    NETWORK_DISRUPTION = "network_disruption"
    DATABASE_CORRUPTION = "database_corruption"
    COMPLETE_REBUILD = "complete_rebuild"
    SERVICE_FAILURE = "service_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"

@dataclass
class RecoveryStep:
    """Individual recovery step"""
    step_name: str
    description: str
    start_time: str
    end_time: Optional[str]
    duration_ms: Optional[float]
    success: bool
    details: Dict[str, Any]
    error: Optional[str] = None

@dataclass
class RecoveryTestResult:
    """Recovery test result"""
    scenario: RecoveryScenario
    timestamp: str
    total_duration_ms: float
    recovery_successful: bool
    steps_completed: List[RecoveryStep]
    pre_failure_state: Dict[str, Any]
    post_recovery_state: Dict[str, Any]
    performance_impact: Dict[str, Any]
    lessons_learned: List[str]
    recommendations: List[str]

class DatabaseRecoveryTester:
    """Complete database recovery testing system"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._load_default_config()
        self.testing_tools = self._initialize_tools()
        self.docker_compose_path = '/home/user/Testing/ai-model-validation-platform'
        self.recovery_results = []
        
    def _load_default_config(self) -> Dict:
        """Load default recovery testing configuration"""
        return {
            'scenarios': {
                RecoveryScenario.CONTAINER_RESTART: {
                    'timeout_seconds': 300,
                    'containers_to_restart': ['postgres', 'backend'],
                    'validation_steps': ['health_check', 'connection_test', 'schema_verification'],
                    'expected_recovery_time_ms': 60000  # 1 minute
                },
                RecoveryScenario.NETWORK_DISRUPTION: {
                    'timeout_seconds': 180,
                    'disruption_duration_seconds': 30,
                    'validation_steps': ['network_test', 'connection_test'],
                    'expected_recovery_time_ms': 30000  # 30 seconds
                },
                RecoveryScenario.DATABASE_CORRUPTION: {
                    'timeout_seconds': 600,
                    'recovery_actions': ['drop_database', 'recreate_schema', 'verify_tables'],
                    'validation_steps': ['schema_verification', 'table_creation_test'],
                    'expected_recovery_time_ms': 120000  # 2 minutes
                },
                RecoveryScenario.COMPLETE_REBUILD: {
                    'timeout_seconds': 900,
                    'recovery_actions': ['stop_all_containers', 'remove_volumes', 'rebuild_from_scratch'],
                    'validation_steps': ['health_check', 'connection_test', 'schema_verification', 'table_creation_test'],
                    'expected_recovery_time_ms': 300000  # 5 minutes
                }
            },
            'validation_criteria': {
                'all_containers_running': True,
                'database_connectivity': True,
                'all_tables_created': True,
                'basic_crud_operations': True,
                'performance_acceptable': True
            },
            'performance_thresholds': {
                'connection_time_ms': 2000,
                'query_response_time_ms': 500,
                'recovery_time_acceptable_ratio': 1.5  # Max 1.5x expected time
            }
        }
    
    def _initialize_tools(self) -> Dict:
        """Initialize all testing tools"""
        tools = {}
        
        try:
            tools['health_checker'] = PostgreSQLHealthChecker()
        except Exception as e:
            logger.warning(f"Could not initialize health checker: {e}")
        
        try:
            tools['network_tester'] = NetworkConnectivityTester()
        except Exception as e:
            logger.warning(f"Could not initialize network tester: {e}")
        
        try:
            tools['connection_validator'] = DatabaseConnectionValidator()
        except Exception as e:
            logger.warning(f"Could not initialize connection validator: {e}")
        
        try:
            tools['schema_verifier'] = DatabaseInitializationVerifier()
        except Exception as e:
            logger.warning(f"Could not initialize schema verifier: {e}")
        
        try:
            tools['table_tester'] = TableCreationTester()
        except Exception as e:
            logger.warning(f"Could not initialize table tester: {e}")
        
        try:
            tools['diagnostic_toolkit'] = DiagnosticToolkit()
        except Exception as e:
            logger.warning(f"Could not initialize diagnostic toolkit: {e}")
        
        return tools
    
    def capture_system_state(self, state_name: str) -> Dict[str, Any]:
        """Capture current system state for comparison"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'state_name': state_name,
            'containers': {},
            'database': {},
            'network': {},
            'performance': {}
        }
        
        try:
            # Capture container states
            result = subprocess.run(
                ['docker-compose', 'ps', '--format', 'json'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Parse container status
                containers_info = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            containers_info.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                
                state['containers'] = {
                    'count': len(containers_info),
                    'running': sum(1 for c in containers_info if c.get('State') == 'running'),
                    'details': containers_info
                }
            
            # Capture database state
            if 'connection_validator' in self.testing_tools:
                validator = self.testing_tools['connection_validator']
                try:
                    db_result = validator.test_raw_psycopg2_connection()
                    state['database'] = {
                        'connected': db_result.success,
                        'connection_time_ms': db_result.duration_ms,
                        'details': db_result.details
                    }
                except Exception as e:
                    state['database'] = {'error': str(e)}
            
            # Capture network state
            if 'network_tester' in self.testing_tools:
                tester = self.testing_tools['network_tester']
                try:
                    # Quick network test
                    postgres_test = tester.test_service_health('postgres')
                    state['network'] = {
                        'postgres_reachable': postgres_test.success,
                        'latency_ms': postgres_test.latency_ms
                    }
                except Exception as e:
                    state['network'] = {'error': str(e)}
            
            # Capture performance metrics
            try:
                import psutil
                state['performance'] = {
                    'cpu_percent': psutil.cpu_percent(interval=0.1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_percent': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
                }
            except Exception as e:
                state['performance'] = {'error': str(e)}
        
        except Exception as e:
            logger.error(f"Failed to capture system state: {e}")
            state['capture_error'] = str(e)
        
        return state
    
    def execute_container_restart_scenario(self) -> RecoveryTestResult:
        """Execute container restart recovery scenario"""
        scenario = RecoveryScenario.CONTAINER_RESTART
        scenario_config = self.config['scenarios'][scenario]
        
        logger.info("Starting container restart recovery scenario...")
        start_time = time.time()
        
        # Capture pre-failure state
        pre_failure_state = self.capture_system_state('pre_failure')
        
        steps = []
        recovery_successful = False
        
        try:
            # Step 1: Stop containers
            step = self._execute_recovery_step(
                'stop_containers',
                'Stopping PostgreSQL and backend containers',
                lambda: self._stop_containers(scenario_config['containers_to_restart'])
            )
            steps.append(step)
            
            if not step.success:
                raise Exception(f"Failed to stop containers: {step.error}")
            
            # Step 2: Wait for containers to stop
            step = self._execute_recovery_step(
                'wait_for_stop',
                'Waiting for containers to stop completely',
                lambda: self._wait_for_containers_to_stop(scenario_config['containers_to_restart'])
            )
            steps.append(step)
            
            # Step 3: Start containers
            step = self._execute_recovery_step(
                'start_containers',
                'Starting containers',
                lambda: self._start_containers(scenario_config['containers_to_restart'])
            )
            steps.append(step)
            
            if not step.success:
                raise Exception(f"Failed to start containers: {step.error}")
            
            # Step 4: Wait for containers to be ready
            step = self._execute_recovery_step(
                'wait_for_ready',
                'Waiting for containers to be ready',
                lambda: self._wait_for_containers_ready(scenario_config['containers_to_restart'], 120)
            )
            steps.append(step)
            
            if not step.success:
                raise Exception(f"Containers did not become ready: {step.error}")
            
            # Step 5: Validate recovery
            step = self._execute_recovery_step(
                'validate_recovery',
                'Validating system recovery',
                lambda: self._validate_recovery(scenario_config['validation_steps'])
            )
            steps.append(step)
            
            recovery_successful = step.success
            
        except Exception as e:
            logger.error(f"Container restart scenario failed: {e}")
            recovery_successful = False
        
        # Capture post-recovery state
        post_recovery_state = self.capture_system_state('post_recovery')
        
        # Calculate performance impact
        performance_impact = self._calculate_performance_impact(pre_failure_state, post_recovery_state)
        
        total_duration = (time.time() - start_time) * 1000
        expected_time = scenario_config['expected_recovery_time_ms']
        
        # Generate lessons learned
        lessons_learned = self._generate_lessons_learned(scenario, steps, total_duration, expected_time)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(scenario, steps, recovery_successful)
        
        result = RecoveryTestResult(
            scenario=scenario,
            timestamp=datetime.now().isoformat(),
            total_duration_ms=round(total_duration, 2),
            recovery_successful=recovery_successful,
            steps_completed=steps,
            pre_failure_state=pre_failure_state,
            post_recovery_state=post_recovery_state,
            performance_impact=performance_impact,
            lessons_learned=lessons_learned,
            recommendations=recommendations
        )
        
        self.recovery_results.append(result)
        return result
    
    def execute_database_corruption_scenario(self) -> RecoveryTestResult:
        """Execute database corruption recovery scenario"""
        scenario = RecoveryScenario.DATABASE_CORRUPTION
        scenario_config = self.config['scenarios'][scenario]
        
        logger.info("Starting database corruption recovery scenario...")
        start_time = time.time()
        
        # Capture pre-failure state
        pre_failure_state = self.capture_system_state('pre_corruption')
        
        steps = []
        recovery_successful = False
        
        try:
            # Step 1: Simulate database corruption (drop all tables)
            step = self._execute_recovery_step(
                'simulate_corruption',
                'Simulating database corruption by dropping tables',
                lambda: self._simulate_database_corruption()
            )
            steps.append(step)
            
            # Step 2: Detect corruption
            step = self._execute_recovery_step(
                'detect_corruption',
                'Detecting database corruption',
                lambda: self._detect_database_issues()
            )
            steps.append(step)
            
            # Step 3: Backup existing data (if any)
            step = self._execute_recovery_step(
                'backup_data',
                'Backing up any recoverable data',
                lambda: self._backup_recoverable_data()
            )
            steps.append(step)
            
            # Step 4: Recreate database schema
            step = self._execute_recovery_step(
                'recreate_schema',
                'Recreating database schema',
                lambda: self._recreate_database_schema()
            )
            steps.append(step)
            
            if not step.success:
                raise Exception(f"Failed to recreate schema: {step.error}")
            
            # Step 5: Verify tables creation
            step = self._execute_recovery_step(
                'verify_tables',
                'Verifying all tables are created correctly',
                lambda: self._verify_all_tables_created()
            )
            steps.append(step)
            
            # Step 6: Test basic operations
            step = self._execute_recovery_step(
                'test_operations',
                'Testing basic CRUD operations',
                lambda: self._test_basic_operations()
            )
            steps.append(step)
            
            recovery_successful = all(s.success for s in steps[-3:])  # Last 3 steps must succeed
            
        except Exception as e:
            logger.error(f"Database corruption scenario failed: {e}")
            recovery_successful = False
        
        # Capture post-recovery state
        post_recovery_state = self.capture_system_state('post_corruption_recovery')
        
        # Calculate performance impact
        performance_impact = self._calculate_performance_impact(pre_failure_state, post_recovery_state)
        
        total_duration = (time.time() - start_time) * 1000
        expected_time = scenario_config['expected_recovery_time_ms']
        
        # Generate lessons learned
        lessons_learned = self._generate_lessons_learned(scenario, steps, total_duration, expected_time)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(scenario, steps, recovery_successful)
        
        result = RecoveryTestResult(
            scenario=scenario,
            timestamp=datetime.now().isoformat(),
            total_duration_ms=round(total_duration, 2),
            recovery_successful=recovery_successful,
            steps_completed=steps,
            pre_failure_state=pre_failure_state,
            post_recovery_state=post_recovery_state,
            performance_impact=performance_impact,
            lessons_learned=lessons_learned,
            recommendations=recommendations
        )
        
        self.recovery_results.append(result)
        return result
    
    def execute_complete_rebuild_scenario(self) -> RecoveryTestResult:
        """Execute complete system rebuild scenario"""
        scenario = RecoveryScenario.COMPLETE_REBUILD
        scenario_config = self.config['scenarios'][scenario]
        
        logger.info("Starting complete rebuild recovery scenario...")
        start_time = time.time()
        
        # Capture pre-failure state
        pre_failure_state = self.capture_system_state('pre_rebuild')
        
        steps = []
        recovery_successful = False
        
        try:
            # Step 1: Stop all containers
            step = self._execute_recovery_step(
                'stop_all_containers',
                'Stopping all Docker containers',
                lambda: self._stop_all_containers()
            )
            steps.append(step)
            
            # Step 2: Remove containers and volumes
            step = self._execute_recovery_step(
                'remove_containers_volumes',
                'Removing containers and volumes',
                lambda: self._remove_containers_and_volumes()
            )
            steps.append(step)
            
            # Step 3: Rebuild and start containers
            step = self._execute_recovery_step(
                'rebuild_containers',
                'Rebuilding and starting containers',
                lambda: self._rebuild_and_start_containers()
            )
            steps.append(step)
            
            if not step.success:
                raise Exception(f"Failed to rebuild containers: {step.error}")
            
            # Step 4: Wait for all services to be ready
            step = self._execute_recovery_step(
                'wait_for_all_ready',
                'Waiting for all services to be ready',
                lambda: self._wait_for_all_services_ready(300)  # 5 minutes
            )
            steps.append(step)
            
            # Step 5: Initialize database
            step = self._execute_recovery_step(
                'initialize_database',
                'Initializing database schema',
                lambda: self._initialize_fresh_database()
            )
            steps.append(step)
            
            # Step 6: Comprehensive validation
            step = self._execute_recovery_step(
                'comprehensive_validation',
                'Running comprehensive system validation',
                lambda: self._run_comprehensive_validation()
            )
            steps.append(step)
            
            recovery_successful = step.success
            
        except Exception as e:
            logger.error(f"Complete rebuild scenario failed: {e}")
            recovery_successful = False
        
        # Capture post-recovery state
        post_recovery_state = self.capture_system_state('post_complete_rebuild')
        
        # Calculate performance impact
        performance_impact = self._calculate_performance_impact(pre_failure_state, post_recovery_state)
        
        total_duration = (time.time() - start_time) * 1000
        expected_time = scenario_config['expected_recovery_time_ms']
        
        # Generate lessons learned
        lessons_learned = self._generate_lessons_learned(scenario, steps, total_duration, expected_time)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(scenario, steps, recovery_successful)
        
        result = RecoveryTestResult(
            scenario=scenario,
            timestamp=datetime.now().isoformat(),
            total_duration_ms=round(total_duration, 2),
            recovery_successful=recovery_successful,
            steps_completed=steps,
            pre_failure_state=pre_failure_state,
            post_recovery_state=post_recovery_state,
            performance_impact=performance_impact,
            lessons_learned=lessons_learned,
            recommendations=recommendations
        )
        
        self.recovery_results.append(result)
        return result
    
    def _execute_recovery_step(self, step_name: str, description: str, action: callable) -> RecoveryStep:
        """Execute individual recovery step"""
        logger.info(f"Executing step: {description}")
        start_time = time.time()
        
        step = RecoveryStep(
            step_name=step_name,
            description=description,
            start_time=datetime.now().isoformat(),
            end_time=None,
            duration_ms=None,
            success=False,
            details={},
            error=None
        )
        
        try:
            result = action()
            step.success = result.get('success', True) if isinstance(result, dict) else bool(result)
            step.details = result if isinstance(result, dict) else {'result': result}
            
        except Exception as e:
            step.success = False
            step.error = str(e)
            step.details = {'exception': str(e), 'traceback': traceback.format_exc()}
            logger.error(f"Step {step_name} failed: {e}")
        
        finally:
            end_time = time.time()
            step.end_time = datetime.now().isoformat()
            step.duration_ms = round((end_time - start_time) * 1000, 2)
            
            status = '✅' if step.success else '❌'
            logger.info(f"{status} {step_name} completed in {step.duration_ms}ms")
        
        return step
    
    def _stop_containers(self, containers: List[str]) -> Dict[str, Any]:
        """Stop specified containers"""
        results = {}
        
        for container in containers:
            result = subprocess.run(
                ['docker-compose', 'stop', container],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True
            )
            
            results[container] = {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        
        all_success = all(r['success'] for r in results.values())
        return {'success': all_success, 'results': results}
    
    def _start_containers(self, containers: List[str]) -> Dict[str, Any]:
        """Start specified containers"""
        results = {}
        
        for container in containers:
            result = subprocess.run(
                ['docker-compose', 'start', container],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True
            )
            
            results[container] = {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        
        all_success = all(r['success'] for r in results.values())
        return {'success': all_success, 'results': results}
    
    def _wait_for_containers_to_stop(self, containers: List[str], timeout: int = 60) -> Dict[str, Any]:
        """Wait for containers to stop completely"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_stopped = True
            
            for container in containers:
                result = subprocess.run(
                    ['docker-compose', 'ps', '-q', container],
                    cwd=self.docker_compose_path,
                    capture_output=True,
                    text=True
                )
                
                if result.stdout.strip():  # Container still exists
                    # Check if it's running
                    status_result = subprocess.run(
                        ['docker', 'inspect', '--format={{.State.Status}}', result.stdout.strip()],
                        capture_output=True,
                        text=True
                    )
                    
                    if status_result.returncode == 0 and 'running' in status_result.stdout:
                        all_stopped = False
                        break
            
            if all_stopped:
                return {'success': True, 'wait_time_ms': (time.time() - start_time) * 1000}
            
            time.sleep(2)
        
        return {'success': False, 'error': 'Timeout waiting for containers to stop'}
    
    def _wait_for_containers_ready(self, containers: List[str], timeout: int = 120) -> Dict[str, Any]:
        """Wait for containers to be ready and healthy"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_ready = True
            container_status = {}
            
            for container in containers:
                if container == 'postgres':
                    # Test PostgreSQL readiness
                    if 'connection_validator' in self.testing_tools:
                        try:
                            validator = self.testing_tools['connection_validator']
                            result = validator.test_raw_psycopg2_connection()
                            container_status[container] = result.success
                            if not result.success:
                                all_ready = False
                        except Exception:
                            container_status[container] = False
                            all_ready = False
                    else:
                        container_status[container] = False
                        all_ready = False
                
                elif container == 'backend':
                    # Test backend readiness (simple Docker health check)
                    result = subprocess.run(
                        ['docker-compose', 'ps', container],
                        cwd=self.docker_compose_path,
                        capture_output=True,
                        text=True
                    )
                    
                    container_ready = result.returncode == 0 and 'Up' in result.stdout
                    container_status[container] = container_ready
                    if not container_ready:
                        all_ready = False
            
            if all_ready:
                return {
                    'success': True, 
                    'wait_time_ms': (time.time() - start_time) * 1000,
                    'container_status': container_status
                }
            
            time.sleep(5)
        
        return {
            'success': False, 
            'error': 'Timeout waiting for containers to be ready',
            'container_status': container_status
        }
    
    def _validate_recovery(self, validation_steps: List[str]) -> Dict[str, Any]:
        """Validate system recovery"""
        validation_results = {}
        overall_success = True
        
        for step in validation_steps:
            if step == 'health_check' and 'health_checker' in self.testing_tools:
                try:
                    checker = self.testing_tools['health_checker']
                    results = checker.run_comprehensive_health_check()
                    summary = checker.get_health_summary(results)
                    
                    step_success = summary['overall_status'] in ['healthy', 'degraded']
                    validation_results[step] = {
                        'success': step_success,
                        'overall_status': summary['overall_status'],
                        'health_score': summary['health_score']
                    }
                    
                    if not step_success:
                        overall_success = False
                        
                except Exception as e:
                    validation_results[step] = {'success': False, 'error': str(e)}
                    overall_success = False
            
            elif step == 'connection_test' and 'connection_validator' in self.testing_tools:
                try:
                    validator = self.testing_tools['connection_validator']
                    result = validator.test_raw_psycopg2_connection()
                    
                    validation_results[step] = {
                        'success': result.success,
                        'connection_time_ms': result.duration_ms
                    }
                    
                    if not result.success:
                        overall_success = False
                        
                except Exception as e:
                    validation_results[step] = {'success': False, 'error': str(e)}
                    overall_success = False
            
            elif step == 'schema_verification' and 'schema_verifier' in self.testing_tools:
                try:
                    verifier = self.testing_tools['schema_verifier']
                    results = verifier.run_comprehensive_verification()
                    
                    validation_results[step] = {
                        'success': results['overall_success'],
                        'tables_exist': results['table_verification']['tables_exist'],
                        'total_tables': results['table_verification']['total_tables']
                    }
                    
                    if not results['overall_success']:
                        overall_success = False
                        
                except Exception as e:
                    validation_results[step] = {'success': False, 'error': str(e)}
                    overall_success = False
        
        return {
            'success': overall_success,
            'validation_results': validation_results
        }
    
    def _simulate_database_corruption(self) -> Dict[str, Any]:
        """Simulate database corruption by dropping tables"""
        try:
            if 'connection_validator' in self.testing_tools:
                # Use raw connection to drop tables
                import psycopg2
                
                conn = psycopg2.connect(
                    host='localhost',
                    port=5432,
                    database='vru_validation',
                    user='postgres',
                    password='secure_password_change_me'
                )
                
                cur = conn.cursor()
                
                # Get all table names
                cur.execute("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public'
                """)
                
                tables = cur.fetchall()
                dropped_tables = []
                
                # Drop all tables
                for table in tables:
                    table_name = table[0]
                    try:
                        cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                        dropped_tables.append(table_name)
                    except Exception as e:
                        logger.warning(f"Could not drop table {table_name}: {e}")
                
                conn.commit()
                cur.close()
                conn.close()
                
                return {
                    'success': True,
                    'tables_dropped': len(dropped_tables),
                    'dropped_tables': dropped_tables
                }
            else:
                return {'success': False, 'error': 'Connection validator not available'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _detect_database_issues(self) -> Dict[str, Any]:
        """Detect database corruption/issues"""
        try:
            if 'diagnostic_toolkit' in self.testing_tools:
                toolkit = self.testing_tools['diagnostic_toolkit']
                result = toolkit.run_quick_diagnostic()
                
                issues_found = len(result.issues_found)
                critical_issues = sum(1 for issue in result.issues_found if issue.severity.value == 'critical')
                
                return {
                    'success': True,
                    'issues_detected': issues_found > 0,
                    'total_issues': issues_found,
                    'critical_issues': critical_issues,
                    'overall_health': result.overall_health
                }
            else:
                return {'success': False, 'error': 'Diagnostic toolkit not available'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _backup_recoverable_data(self) -> Dict[str, Any]:
        """Backup any recoverable data"""
        # In this simulation, we don't have data to backup
        # In a real scenario, this would backup user data, configurations, etc.
        return {
            'success': True,
            'backup_created': False,
            'reason': 'No user data to backup in test scenario'
        }
    
    def _recreate_database_schema(self) -> Dict[str, Any]:
        """Recreate database schema"""
        try:
            if 'schema_verifier' in self.testing_tools:
                verifier = self.testing_tools['schema_verifier']
                result = verifier.initialize_database_schema()
                
                return {
                    'success': result['success'],
                    'tables_created': len(result.get('new_tables', [])),
                    'total_tables': result.get('total_tables', 0),
                    'details': result
                }
            else:
                return {'success': False, 'error': 'Schema verifier not available'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_all_tables_created(self) -> Dict[str, Any]:
        """Verify all tables are created correctly"""
        try:
            if 'table_tester' in self.testing_tools:
                tester = self.testing_tools['table_tester']
                # Just verify tables exist without recreating them
                
                # Use schema verifier instead for verification
                if 'schema_verifier' in self.testing_tools:
                    verifier = self.testing_tools['schema_verifier']
                    results = verifier.run_comprehensive_verification()
                    
                    table_info = results['table_verification']
                    
                    return {
                        'success': results['overall_success'],
                        'tables_exist': table_info['tables_exist'],
                        'total_tables': table_info['total_tables'],
                        'missing_tables': table_info['total_tables'] - table_info['tables_exist']
                    }
                else:
                    return {'success': False, 'error': 'Schema verifier not available'}
            else:
                return {'success': False, 'error': 'Table tester not available'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_basic_operations(self) -> Dict[str, Any]:
        """Test basic CRUD operations"""
        try:
            # Test basic database operations
            if 'connection_validator' in self.testing_tools:
                validator = self.testing_tools['connection_validator']
                result = validator.test_orm_functionality()
                
                return {
                    'success': result.success,
                    'details': result.details
                }
            else:
                return {'success': False, 'error': 'Connection validator not available'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _stop_all_containers(self) -> Dict[str, Any]:
        """Stop all Docker containers"""
        try:
            result = subprocess.run(
                ['docker-compose', 'down'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _remove_containers_and_volumes(self) -> Dict[str, Any]:
        """Remove containers and volumes"""
        try:
            # Remove containers and volumes
            result = subprocess.run(
                ['docker-compose', 'down', '-v', '--remove-orphans'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=180
            )
            
            success = result.returncode == 0
            
            # Also remove any dangling volumes
            if success:
                subprocess.run(
                    ['docker', 'volume', 'prune', '-f'],
                    capture_output=True,
                    text=True
                )
            
            return {
                'success': success,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _rebuild_and_start_containers(self) -> Dict[str, Any]:
        """Rebuild and start containers"""
        try:
            # Build and start containers
            result = subprocess.run(
                ['docker-compose', 'up', '-d', '--build'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes for build
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _wait_for_all_services_ready(self, timeout: int = 300) -> Dict[str, Any]:
        """Wait for all services to be ready"""
        # Similar to _wait_for_containers_ready but for all services
        return self._wait_for_containers_ready(['postgres', 'backend'], timeout)
    
    def _initialize_fresh_database(self) -> Dict[str, Any]:
        """Initialize fresh database"""
        try:
            if 'schema_verifier' in self.testing_tools:
                verifier = self.testing_tools['schema_verifier']
                result = verifier.initialize_database_schema()
                
                return {
                    'success': result['success'],
                    'initialization_log': result.get('initialization_log', []),
                    'tables_created': len(result.get('new_tables', [])),
                    'total_tables': result.get('total_tables', 0)
                }
            else:
                return {'success': False, 'error': 'Schema verifier not available'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive system validation"""
        try:
            if 'diagnostic_toolkit' in self.testing_tools:
                toolkit = self.testing_tools['diagnostic_toolkit']
                result = toolkit.run_comprehensive_diagnostic()
                
                return {
                    'success': result.overall_health in ['healthy', 'minor_issues'],
                    'overall_health': result.overall_health,
                    'issues_found': len(result.issues_found),
                    'test_success_rate': result.summary['test_success_rate']
                }
            else:
                return {'success': False, 'error': 'Diagnostic toolkit not available'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _calculate_performance_impact(self, pre_state: Dict, post_state: Dict) -> Dict[str, Any]:
        """Calculate performance impact of recovery"""
        impact = {
            'connection_time_change_ms': 0,
            'memory_usage_change_percent': 0,
            'cpu_usage_change_percent': 0,
            'recovery_overhead': 'unknown'
        }
        
        try:
            # Compare database connection times
            pre_db = pre_state.get('database', {})
            post_db = post_state.get('database', {})
            
            if pre_db.get('connection_time_ms') and post_db.get('connection_time_ms'):
                impact['connection_time_change_ms'] = (
                    post_db['connection_time_ms'] - pre_db['connection_time_ms']
                )
            
            # Compare performance metrics
            pre_perf = pre_state.get('performance', {})
            post_perf = post_state.get('performance', {})
            
            if pre_perf.get('memory_percent') and post_perf.get('memory_percent'):
                impact['memory_usage_change_percent'] = (
                    post_perf['memory_percent'] - pre_perf['memory_percent']
                )
            
            if pre_perf.get('cpu_percent') and post_perf.get('cpu_percent'):
                impact['cpu_usage_change_percent'] = (
                    post_perf['cpu_percent'] - pre_perf['cpu_percent']
                )
            
            # Determine overall recovery overhead
            if (abs(impact['connection_time_change_ms']) < 100 and
                abs(impact['memory_usage_change_percent']) < 5 and
                abs(impact['cpu_usage_change_percent']) < 10):
                impact['recovery_overhead'] = 'minimal'
            elif (abs(impact['connection_time_change_ms']) < 500 and
                  abs(impact['memory_usage_change_percent']) < 15 and
                  abs(impact['cpu_usage_change_percent']) < 25):
                impact['recovery_overhead'] = 'acceptable'
            else:
                impact['recovery_overhead'] = 'significant'
        
        except Exception as e:
            impact['calculation_error'] = str(e)
        
        return impact
    
    def _generate_lessons_learned(self, scenario: RecoveryScenario, steps: List[RecoveryStep], 
                                 total_duration: float, expected_time: float) -> List[str]:
        """Generate lessons learned from recovery test"""
        lessons = []
        
        # Duration analysis
        if total_duration > expected_time * 1.5:
            lessons.append(f"Recovery took {total_duration/expected_time:.1f}x longer than expected - optimization needed")
        elif total_duration < expected_time * 0.5:
            lessons.append(f"Recovery was faster than expected - {scenario.value} recovery is well-optimized")
        
        # Step analysis
        failed_steps = [step for step in steps if not step.success]
        if failed_steps:
            lessons.append(f"Failed steps: {', '.join(step.step_name for step in failed_steps)}")
        
        # Longest steps
        longest_step = max(steps, key=lambda s: s.duration_ms or 0, default=None)
        if longest_step and longest_step.duration_ms and longest_step.duration_ms > total_duration * 0.4:
            lessons.append(f"Step '{longest_step.step_name}' took {longest_step.duration_ms/total_duration:.1f}% of total time")
        
        # Scenario-specific lessons
        if scenario == RecoveryScenario.CONTAINER_RESTART:
            lessons.append("Container restart recovery requires proper health checks before proceeding")
        elif scenario == RecoveryScenario.DATABASE_CORRUPTION:
            lessons.append("Database corruption recovery benefits from automated schema recreation")
        elif scenario == RecoveryScenario.COMPLETE_REBUILD:
            lessons.append("Complete rebuild is most reliable but slowest recovery method")
        
        return lessons
    
    def _generate_recommendations(self, scenario: RecoveryScenario, steps: List[RecoveryStep], 
                                 recovery_successful: bool) -> List[str]:
        """Generate recommendations based on recovery test results"""
        recommendations = []
        
        if not recovery_successful:
            recommendations.append("Recovery failed - immediate investigation required")
            recommendations.append("Review failed steps and implement fixes")
        
        # Performance recommendations
        slow_steps = [step for step in steps if step.duration_ms and step.duration_ms > 30000]  # > 30s
        if slow_steps:
            recommendations.append(f"Optimize slow steps: {', '.join(step.step_name for step in slow_steps)}")
        
        # Reliability recommendations
        failed_steps = [step for step in steps if not step.success]
        if failed_steps:
            recommendations.append("Add retry logic for failed steps")
            recommendations.append("Implement better error handling and rollback mechanisms")
        
        # Scenario-specific recommendations
        if scenario == RecoveryScenario.CONTAINER_RESTART:
            recommendations.append("Implement health check endpoints for faster readiness detection")
            recommendations.append("Consider graceful shutdown procedures")
        elif scenario == RecoveryScenario.DATABASE_CORRUPTION:
            recommendations.append("Implement automated backup before corruption scenarios")
            recommendations.append("Create database migration scripts for faster schema recreation")
        elif scenario == RecoveryScenario.COMPLETE_REBUILD:
            recommendations.append("Optimize Docker image build times")
            recommendations.append("Consider using pre-built images for faster deployment")
        
        # General recommendations
        recommendations.append("Document recovery procedures for operations team")
        recommendations.append("Schedule regular recovery testing")
        
        return recommendations
    
    def run_all_recovery_scenarios(self) -> List[RecoveryTestResult]:
        """Run all recovery scenarios"""
        scenarios = [
            self.execute_container_restart_scenario,
            self.execute_database_corruption_scenario,
            self.execute_complete_rebuild_scenario
        ]
        
        results = []
        
        for scenario_func in scenarios:
            try:
                logger.info(f"Running {scenario_func.__name__}...")
                result = scenario_func()
                results.append(result)
                
                # Wait between scenarios
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Scenario {scenario_func.__name__} crashed: {e}")
        
        return results
    
    def save_recovery_report(self, results: List[RecoveryTestResult], filename: str = None) -> str:
        """Save recovery test report"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/home/user/Testing/ai-model-validation-platform/backend/logs/recovery_test_report_{timestamp}.json'
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        report_data = {
            'report_timestamp': datetime.now().isoformat(),
            'total_scenarios': len(results),
            'successful_scenarios': sum(1 for r in results if r.recovery_successful),
            'scenario_results': [asdict(result) for result in results],
            'overall_summary': self._generate_overall_summary(results)
        }
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return filename
    
    def _generate_overall_summary(self, results: List[RecoveryTestResult]) -> Dict[str, Any]:
        """Generate overall summary of all recovery tests"""
        if not results:
            return {}
        
        successful = sum(1 for r in results if r.recovery_successful)
        total_duration = sum(r.total_duration_ms for r in results)
        avg_duration = total_duration / len(results)
        
        return {
            'success_rate': (successful / len(results)) * 100,
            'total_test_time_ms': round(total_duration, 2),
            'average_recovery_time_ms': round(avg_duration, 2),
            'fastest_recovery_ms': min(r.total_duration_ms for r in results),
            'slowest_recovery_ms': max(r.total_duration_ms for r in results),
            'most_reliable_scenario': max(results, key=lambda r: 1 if r.recovery_successful else 0).scenario.value,
            'recommendations': [
                'Implement automated recovery procedures',
                'Schedule regular recovery testing',
                'Optimize slow recovery scenarios',
                'Document lessons learned'
            ]
        }
    
    def generate_recovery_report_text(self, results: List[RecoveryTestResult]) -> str:
        """Generate human-readable recovery test report"""
        if not results:
            return "No recovery test results available."
        
        report = []
        report.append("# Database Recovery Test Report")
        report.append(f"Generated: {datetime.now().isoformat()}\n")
        
        # Overall summary
        summary = self._generate_overall_summary(results)
        successful = sum(1 for r in results if r.recovery_successful)
        
        report.append(f"## Overall Results")
        report.append(f"- Scenarios Tested: {len(results)}")
        report.append(f"- Successful Recoveries: {successful}/{len(results)} ({summary['success_rate']:.1f}%)")
        report.append(f"- Total Test Time: {summary['total_test_time_ms']/1000:.1f} seconds")
        report.append(f"- Average Recovery Time: {summary['average_recovery_time_ms']/1000:.1f} seconds\n")
        
        # Individual scenario results
        for i, result in enumerate(results, 1):
            status = '✅' if result.recovery_successful else '❌'
            report.append(f"## {i}. {status} {result.scenario.value.replace('_', ' ').title()}")
            report.append(f"**Duration:** {result.total_duration_ms/1000:.1f} seconds")
            report.append(f"**Steps Completed:** {len(result.steps_completed)}")
            report.append(f"**Successful Steps:** {sum(1 for s in result.steps_completed if s.success)}/{len(result.steps_completed)}")
            
            # Failed steps
            failed_steps = [s for s in result.steps_completed if not s.success]
            if failed_steps:
                report.append(f"**Failed Steps:** {', '.join(s.step_name for s in failed_steps)}")
            
            # Performance impact
            if result.performance_impact.get('recovery_overhead') != 'unknown':
                report.append(f"**Performance Impact:** {result.performance_impact['recovery_overhead']}")
            
            # Key lessons
            if result.lessons_learned:
                report.append("**Key Lessons:**")
                for lesson in result.lessons_learned[:3]:  # Top 3 lessons
                    report.append(f"  - {lesson}")
            
            report.append("")
        
        # Overall recommendations
        if summary.get('recommendations'):
            report.append("## 💡 Overall Recommendations")
            for rec in summary['recommendations']:
                report.append(f"- {rec}")
        
        return "\n".join(report)

def main():
    """Main recovery testing execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Recovery Testing Tool')
    parser.add_argument('--scenario', choices=['container_restart', 'database_corruption', 'complete_rebuild', 'all'],
                       default='all', help='Recovery scenario to test')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--report', action='store_true', help='Generate human-readable report')
    parser.add_argument('--config', help='Custom configuration file')
    
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
    
    # Create recovery tester
    tester = DatabaseRecoveryTester(config)
    
    # Run specified scenario(s)
    if args.scenario == 'all':
        print("\nRunning all recovery scenarios...")
        results = tester.run_all_recovery_scenarios()
    elif args.scenario == 'container_restart':
        print("\nRunning container restart scenario...")
        results = [tester.execute_container_restart_scenario()]
    elif args.scenario == 'database_corruption':
        print("\nRunning database corruption scenario...")
        results = [tester.execute_database_corruption_scenario()]
    elif args.scenario == 'complete_rebuild':
        print("\nRunning complete rebuild scenario...")
        results = [tester.execute_complete_rebuild_scenario()]
    else:
        print(f"Unknown scenario: {args.scenario}")
        return
    
    # Display summary
    successful = sum(1 for r in results if r.recovery_successful)
    total_time = sum(r.total_duration_ms for r in results) / 1000
    
    print(f"\n=== Recovery Test Results ===")
    print(f"Scenarios: {len(results)}")
    print(f"Successful: {successful}/{len(results)} ({(successful/len(results))*100:.1f}%)")
    print(f"Total Time: {total_time:.1f} seconds")
    
    for result in results:
        status = '✅' if result.recovery_successful else '❌'
        print(f"{status} {result.scenario.value}: {result.total_duration_ms/1000:.1f}s")
    
    # Save results
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'/home/user/Testing/ai-model-validation-platform/backend/logs/recovery_test_{timestamp}.json'
    
    saved_file = tester.save_recovery_report(results, output_file)
    print(f"\nResults saved to: {saved_file}")
    
    # Generate report if requested
    if args.report:
        report = tester.generate_recovery_report_text(results)
        report_file = saved_file.replace('.json', '_report.md')
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"Report saved to: {report_file}")
        print(f"\n{report}")

if __name__ == '__main__':
    main()
