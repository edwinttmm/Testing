#!/usr/bin/env python3
"""
Comprehensive Troubleshooting Diagnostics Toolkit

An integrated diagnostic system that combines all database testing tools
to provide comprehensive troubleshooting capabilities and recovery recommendations.

Features:
- Unified diagnostic interface
- Automated problem detection and classification
- Step-by-step troubleshooting workflows
- Recovery action recommendations
- Historical issue tracking
- Performance impact analysis
- Multi-level diagnostic depth
"""

import os
import sys
import json
import time
import logging
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
except ImportError as e:
    print(f"Warning: Some diagnostic modules unavailable: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DiagnosticLevel(Enum):
    """Diagnostic depth levels"""
    QUICK = "quick"  # Basic connectivity and status checks
    STANDARD = "standard"  # Full health checks and validation
    COMPREHENSIVE = "comprehensive"  # All tests including stress testing
    DEEP = "deep"  # Detailed analysis with performance profiling

class IssueSeverity(Enum):
    """Issue severity levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class DiagnosticIssue:
    """Diagnostic issue data structure"""
    id: str
    timestamp: str
    severity: IssueSeverity
    category: str
    component: str
    title: str
    description: str
    symptoms: List[str]
    root_cause: Optional[str]
    impact: str
    recommendations: List[str]
    recovery_actions: List[str]
    related_issues: List[str]
    details: Dict[str, Any]

@dataclass
class DiagnosticResult:
    """Overall diagnostic result"""
    timestamp: str
    diagnostic_level: DiagnosticLevel
    duration_ms: float
    overall_health: str
    issues_found: List[DiagnosticIssue]
    components_tested: List[str]
    test_results: Dict[str, Any]
    recommendations: List[str]
    recovery_plan: List[str]
    summary: Dict[str, Any]

class DiagnosticToolkit:
    """Comprehensive diagnostic toolkit"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._load_default_config()
        self.diagnostic_tools = self._initialize_tools()
        self.issue_database = []  # Store historical issues
        self.known_issues = self._load_known_issues()
        
    def _load_default_config(self) -> Dict:
        """Load default diagnostic configuration"""
        return {
            'diagnostic_levels': {
                DiagnosticLevel.QUICK: {
                    'timeout_seconds': 60,
                    'tests': ['basic_connectivity', 'container_status'],
                    'parallel_execution': True
                },
                DiagnosticLevel.STANDARD: {
                    'timeout_seconds': 300,
                    'tests': ['health_check', 'network_test', 'connection_validation'],
                    'parallel_execution': True
                },
                DiagnosticLevel.COMPREHENSIVE: {
                    'timeout_seconds': 900,
                    'tests': ['health_check', 'network_test', 'connection_validation', 'schema_verification', 'table_creation'],
                    'parallel_execution': False  # Sequential for comprehensive testing
                },
                DiagnosticLevel.DEEP: {
                    'timeout_seconds': 1800,
                    'tests': ['health_check', 'network_test', 'connection_validation', 'schema_verification', 'table_creation', 'performance_analysis'],
                    'parallel_execution': False,
                    'include_profiling': True
                }
            },
            'issue_thresholds': {
                'connection_time_ms': {'high': 1000, 'critical': 5000},
                'success_rate_percent': {'high': 90, 'critical': 70},
                'missing_tables_count': {'medium': 1, 'critical': 3},
                'memory_usage_percent': {'high': 85, 'critical': 95},
                'cpu_usage_percent': {'high': 80, 'critical': 95}
            },
            'recovery_actions': {
                'restart_containers': {'enabled': True, 'risk': 'medium'},
                'recreate_database': {'enabled': True, 'risk': 'high'},
                'clear_cache': {'enabled': True, 'risk': 'low'},
                'rebuild_indexes': {'enabled': True, 'risk': 'medium'}
            }
        }
    
    def _initialize_tools(self) -> Dict:
        """Initialize all diagnostic tools"""
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
        
        return tools
    
    def _load_known_issues(self) -> Dict[str, Dict]:
        """Load database of known issues and their solutions"""
        return {
            'postgres_connection_refused': {
                'symptoms': ['Connection refused', 'could not connect to server'],
                'causes': ['PostgreSQL container not running', 'Network connectivity issues', 'Port binding problems'],
                'solutions': ['Restart postgres container', 'Check Docker network', 'Verify port configuration']
            },
            'database_not_found': {
                'symptoms': ['database "vru_validation" does not exist'],
                'causes': ['Database not created', 'Connection to wrong database'],
                'solutions': ['Create database', 'Run database initialization', 'Check connection URL']
            },
            'table_missing': {
                'symptoms': ['relation "projects" does not exist', 'table not found'],
                'causes': ['Database schema not initialized', 'Tables were dropped', 'Migration failed'],
                'solutions': ['Run database initialization', 'Execute schema creation', 'Check migration scripts']
            },
            'foreign_key_constraint': {
                'symptoms': ['violates foreign key constraint', 'Key (project_id)'],
                'causes': ['Referenced record does not exist', 'Data integrity issue'],
                'solutions': ['Create referenced records', 'Fix data relationships', 'Check constraint definitions']
            },
            'connection_pool_exhausted': {
                'symptoms': ['connection pool is exhausted', 'QueuePool limit', 'timeout occurred'],
                'causes': ['Too many concurrent connections', 'Connection leaks', 'Pool configuration too small'],
                'solutions': ['Increase pool size', 'Fix connection leaks', 'Optimize query patterns']
            },
            'disk_space_full': {
                'symptoms': ['No space left on device', 'disk full', 'cannot extend'],
                'causes': ['Insufficient disk space', 'Log files too large', 'Data growth'],
                'solutions': ['Clean up disk space', 'Rotate log files', 'Archive old data']
            },
            'memory_exhausted': {
                'symptoms': ['out of memory', 'cannot allocate memory', 'killed by signal 9'],
                'causes': ['Insufficient memory', 'Memory leaks', 'Large queries'],
                'solutions': ['Increase memory allocation', 'Optimize queries', 'Fix memory leaks']
            }
        }
    
    def run_quick_diagnostic(self) -> DiagnosticResult:
        """Run quick diagnostic (basic connectivity and status)"""
        return self._run_diagnostic(DiagnosticLevel.QUICK)
    
    def run_standard_diagnostic(self) -> DiagnosticResult:
        """Run standard diagnostic (full health checks)"""
        return self._run_diagnostic(DiagnosticLevel.STANDARD)
    
    def run_comprehensive_diagnostic(self) -> DiagnosticResult:
        """Run comprehensive diagnostic (all tests)"""
        return self._run_diagnostic(DiagnosticLevel.COMPREHENSIVE)
    
    def run_deep_diagnostic(self) -> DiagnosticResult:
        """Run deep diagnostic (detailed analysis with profiling)"""
        return self._run_diagnostic(DiagnosticLevel.DEEP)
    
    def _run_diagnostic(self, level: DiagnosticLevel) -> DiagnosticResult:
        """Run diagnostic at specified level"""
        logger.info(f"Starting {level.value} diagnostic...")
        start_time = time.time()
        
        level_config = self.config['diagnostic_levels'][level]
        test_results = {}
        issues_found = []
        components_tested = []
        
        # Determine tests to run
        tests_to_run = level_config['tests']
        parallel_execution = level_config['parallel_execution']
        
        if parallel_execution:
            test_results = self._run_tests_parallel(tests_to_run, level_config['timeout_seconds'])
        else:
            test_results = self._run_tests_sequential(tests_to_run, level_config['timeout_seconds'])
        
        # Analyze results and identify issues
        for test_name, result in test_results.items():
            components_tested.append(test_name)
            test_issues = self._analyze_test_result(test_name, result, level)
            issues_found.extend(test_issues)
        
        # Classify overall health
        overall_health = self._determine_overall_health(issues_found)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(issues_found, level)
        
        # Generate recovery plan
        recovery_plan = self._generate_recovery_plan(issues_found, level)
        
        # Create summary
        summary = self._generate_summary(test_results, issues_found)
        
        duration = (time.time() - start_time) * 1000
        
        result = DiagnosticResult(
            timestamp=datetime.now().isoformat(),
            diagnostic_level=level,
            duration_ms=round(duration, 2),
            overall_health=overall_health,
            issues_found=issues_found,
            components_tested=components_tested,
            test_results=test_results,
            recommendations=recommendations,
            recovery_plan=recovery_plan,
            summary=summary
        )
        
        # Store in issue database
        self.issue_database.append(result)
        
        logger.info(f"{level.value.title()} diagnostic completed in {duration:.2f}ms - "
                   f"Health: {overall_health}, Issues: {len(issues_found)}")
        
        return result
    
    def _run_tests_parallel(self, tests: List[str], timeout: int) -> Dict[str, Any]:
        """Run tests in parallel"""
        results = {}
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit test tasks
            futures = {}
            for test_name in tests:
                if test_name in self._get_test_methods():
                    future = executor.submit(self._execute_test, test_name)
                    futures[future] = test_name
            
            # Collect results with timeout
            for future in as_completed(futures, timeout=timeout):
                test_name = futures[future]
                try:
                    results[test_name] = future.result()
                except Exception as e:
                    logger.error(f"Test {test_name} failed: {e}")
                    results[test_name] = {
                        'success': False,
                        'error': str(e),
                        'traceback': traceback.format_exc()
                    }
        
        return results
    
    def _run_tests_sequential(self, tests: List[str], timeout: int) -> Dict[str, Any]:
        """Run tests sequentially"""
        results = {}
        start_time = time.time()
        
        for test_name in tests:
            if time.time() - start_time > timeout:
                logger.warning(f"Diagnostic timeout reached, skipping remaining tests")
                break
            
            try:
                results[test_name] = self._execute_test(test_name)
            except Exception as e:
                logger.error(f"Test {test_name} failed: {e}")
                results[test_name] = {
                    'success': False,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }
        
        return results
    
    def _get_test_methods(self) -> Dict[str, callable]:
        """Get mapping of test names to methods"""
        return {
            'basic_connectivity': self._test_basic_connectivity,
            'container_status': self._test_container_status,
            'health_check': self._test_health_check,
            'network_test': self._test_network_connectivity,
            'connection_validation': self._test_connection_validation,
            'schema_verification': self._test_schema_verification,
            'table_creation': self._test_table_creation,
            'performance_analysis': self._test_performance_analysis
        }
    
    def _execute_test(self, test_name: str) -> Dict[str, Any]:
        """Execute individual test"""
        test_methods = self._get_test_methods()
        
        if test_name not in test_methods:
            return {
                'success': False,
                'error': f'Unknown test: {test_name}'
            }
        
        start_time = time.time()
        try:
            result = test_methods[test_name]()
            result['duration_ms'] = round((time.time() - start_time) * 1000, 2)
            return result
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc(),
                'duration_ms': round((time.time() - start_time) * 1000, 2)
            }
    
    def _test_basic_connectivity(self) -> Dict[str, Any]:
        """Test basic database connectivity"""
        try:
            # Simple connection test
            if 'connection_validator' in self.diagnostic_tools:
                validator = self.diagnostic_tools['connection_validator']
                result = validator.test_raw_psycopg2_connection()
                
                return {
                    'success': result.success,
                    'connection_time_ms': result.duration_ms,
                    'details': result.details,
                    'error': result.error
                }
            else:
                return {
                    'success': False,
                    'error': 'Connection validator not available'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_container_status(self) -> Dict[str, Any]:
        """Test Docker container status"""
        try:
            if 'health_checker' in self.diagnostic_tools:
                checker = self.diagnostic_tools['health_checker']
                postgres_result = checker.check_docker_container_health('postgres')
                backend_result = checker.check_docker_container_health('backend')
                
                return {
                    'success': postgres_result.status == 'healthy' and backend_result.status == 'healthy',
                    'postgres_status': postgres_result.status,
                    'backend_status': backend_result.status,
                    'postgres_details': postgres_result.details,
                    'backend_details': backend_result.details
                }
            else:
                return {
                    'success': False,
                    'error': 'Health checker not available'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        try:
            if 'health_checker' in self.diagnostic_tools:
                checker = self.diagnostic_tools['health_checker']
                results = checker.run_comprehensive_health_check()
                summary = checker.get_health_summary(results)
                
                return {
                    'success': summary['overall_status'] == 'healthy',
                    'overall_status': summary['overall_status'],
                    'health_score': summary['health_score'],
                    'critical_issues': summary['critical_issues'],
                    'warnings': summary['warnings'],
                    'recommendations': summary['recommendations'],
                    'detailed_results': summary['detailed_results']
                }
            else:
                return {
                    'success': False,
                    'error': 'Health checker not available'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_network_connectivity(self) -> Dict[str, Any]:
        """Test network connectivity"""
        try:
            if 'network_tester' in self.diagnostic_tools:
                tester = self.diagnostic_tools['network_tester']
                results = tester.run_comprehensive_network_test()
                
                return {
                    'success': results['successful_tests'] == results['total_tests'],
                    'success_rate': results['successful_tests'] / max(results['total_tests'], 1) * 100,
                    'total_tests': results['total_tests'],
                    'successful_tests': results['successful_tests'],
                    'average_latency_ms': results['average_latency_ms'],
                    'recommendations': results['recommendations'],
                    'test_categories': results['test_categories']
                }
            else:
                return {
                    'success': False,
                    'error': 'Network tester not available'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_connection_validation(self) -> Dict[str, Any]:
        """Test database connection validation"""
        try:
            if 'connection_validator' in self.diagnostic_tools:
                validator = self.diagnostic_tools['connection_validator']
                results = validator.run_comprehensive_validation()
                
                return {
                    'success': results['overall_status'] == 'healthy',
                    'overall_status': results['overall_status'],
                    'success_rate': results['success_rate'],
                    'average_connection_time_ms': results['average_connection_time_ms'],
                    'successful_tests': results['successful_tests'],
                    'total_tests': results['total_tests'],
                    'recommendations': results['recommendations']
                }
            else:
                return {
                    'success': False,
                    'error': 'Connection validator not available'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_schema_verification(self) -> Dict[str, Any]:
        """Test database schema verification"""
        try:
            if 'schema_verifier' in self.diagnostic_tools:
                verifier = self.diagnostic_tools['schema_verifier']
                results = verifier.run_comprehensive_verification()
                
                table_info = results['table_verification']
                
                return {
                    'success': results['overall_success'],
                    'overall_success': results['overall_success'],
                    'tables_exist': table_info['tables_exist'],
                    'total_tables': table_info['total_tables'],
                    'tables_valid': table_info['tables_valid'],
                    'missing_tables': table_info['total_tables'] - table_info['tables_exist'],
                    'recommendations': results['recommendations'],
                    'summary': results['summary']
                }
            else:
                return {
                    'success': False,
                    'error': 'Schema verifier not available'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_table_creation(self) -> Dict[str, Any]:
        """Test table creation"""
        try:
            if 'table_tester' in self.diagnostic_tools:
                tester = self.diagnostic_tools['table_tester']
                results = tester.run_comprehensive_table_creation_test()
                
                table_results = results['table_creation_results']
                
                return {
                    'success': results['overall_success'],
                    'overall_success': results['overall_success'],
                    'successful_creations': table_results['successful_creations'],
                    'total_tables': table_results['total_tables'],
                    'valid_structures': table_results['valid_structures'],
                    'average_creation_time_ms': table_results['average_creation_time_ms'],
                    'recommendations': results['recommendations'],
                    'summary': results['summary']
                }
            else:
                return {
                    'success': False,
                    'error': 'Table tester not available'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_performance_analysis(self) -> Dict[str, Any]:
        """Test performance analysis"""
        try:
            # This is a placeholder for performance analysis
            # In a real implementation, you would collect various performance metrics
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            performance_score = 100
            issues = []
            
            if cpu_percent > 80:
                performance_score -= 20
                issues.append(f'High CPU usage: {cpu_percent:.1f}%')
            
            if memory.percent > 85:
                performance_score -= 20
                issues.append(f'High memory usage: {memory.percent:.1f}%')
            
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > 90:
                performance_score -= 20
                issues.append(f'High disk usage: {disk_percent:.1f}%')
            
            return {
                'success': performance_score > 60,
                'performance_score': performance_score,
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk_percent,
                'issues': issues,
                'system_info': {
                    'cpu_cores': psutil.cpu_count(),
                    'total_memory_gb': round(memory.total / (1024**3), 2),
                    'total_disk_gb': round(disk.total / (1024**3), 2)
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _analyze_test_result(self, test_name: str, result: Dict[str, Any], level: DiagnosticLevel) -> List[DiagnosticIssue]:
        """Analyze test result and identify issues"""
        issues = []
        
        if not result.get('success', False):
            # Test failed - create critical issue
            issue_id = f"{test_name}_failure_{int(time.time())}"
            
            # Try to match against known issues
            error_text = result.get('error', '').lower()
            matched_issue = None
            
            for issue_type, issue_info in self.known_issues.items():
                for symptom in issue_info['symptoms']:
                    if symptom.lower() in error_text:
                        matched_issue = issue_info
                        break
                if matched_issue:
                    break
            
            if matched_issue:
                issue = DiagnosticIssue(
                    id=issue_id,
                    timestamp=datetime.now().isoformat(),
                    severity=IssueSeverity.CRITICAL,
                    category='test_failure',
                    component=test_name,
                    title=f'{test_name} test failed - Known Issue',
                    description=f'Test {test_name} failed with known error pattern',
                    symptoms=[error_text],
                    root_cause=', '.join(matched_issue['causes']),
                    impact='System functionality may be impaired',
                    recommendations=matched_issue['solutions'],
                    recovery_actions=matched_issue['solutions'],
                    related_issues=[],
                    details=result
                )
            else:
                issue = DiagnosticIssue(
                    id=issue_id,
                    timestamp=datetime.now().isoformat(),
                    severity=IssueSeverity.CRITICAL,
                    category='test_failure',
                    component=test_name,
                    title=f'{test_name} test failed',
                    description=f'Test {test_name} failed with error: {result.get("error", "Unknown error")}',
                    symptoms=[error_text],
                    root_cause=None,
                    impact='System functionality may be impaired',
                    recommendations=['Check logs for more details', 'Restart affected services', 'Verify configuration'],
                    recovery_actions=['Investigate error cause', 'Apply targeted fixes'],
                    related_issues=[],
                    details=result
                )
            
            issues.append(issue)
        
        else:
            # Test succeeded - check for performance or warning issues
            performance_issues = self._check_performance_thresholds(test_name, result)
            issues.extend(performance_issues)
        
        return issues
    
    def _check_performance_thresholds(self, test_name: str, result: Dict[str, Any]) -> List[DiagnosticIssue]:
        """Check result against performance thresholds"""
        issues = []
        thresholds = self.config['issue_thresholds']
        
        # Check connection time
        if 'connection_time_ms' in result:
            conn_time = result['connection_time_ms']
            if conn_time >= thresholds['connection_time_ms']['critical']:
                issues.append(self._create_performance_issue(
                    test_name, 'connection_time', conn_time, IssueSeverity.CRITICAL,
                    'Very slow database connection', result
                ))
            elif conn_time >= thresholds['connection_time_ms']['high']:
                issues.append(self._create_performance_issue(
                    test_name, 'connection_time', conn_time, IssueSeverity.HIGH,
                    'Slow database connection', result
                ))
        
        # Check success rate
        if 'success_rate' in result:
            success_rate = result['success_rate']
            if success_rate <= thresholds['success_rate_percent']['critical']:
                issues.append(self._create_performance_issue(
                    test_name, 'success_rate', success_rate, IssueSeverity.CRITICAL,
                    'Very low success rate', result
                ))
            elif success_rate <= thresholds['success_rate_percent']['high']:
                issues.append(self._create_performance_issue(
                    test_name, 'success_rate', success_rate, IssueSeverity.HIGH,
                    'Low success rate', result
                ))
        
        # Check missing tables
        if 'missing_tables' in result:
            missing_count = result['missing_tables']
            if missing_count >= thresholds['missing_tables_count']['critical']:
                issues.append(self._create_performance_issue(
                    test_name, 'missing_tables', missing_count, IssueSeverity.CRITICAL,
                    'Multiple database tables missing', result
                ))
            elif missing_count >= thresholds['missing_tables_count']['medium']:
                issues.append(self._create_performance_issue(
                    test_name, 'missing_tables', missing_count, IssueSeverity.MEDIUM,
                    'Database tables missing', result
                ))
        
        return issues
    
    def _create_performance_issue(self, test_name: str, metric: str, value: float, severity: IssueSeverity, description: str, details: Dict) -> DiagnosticIssue:
        """Create performance-related issue"""
        issue_id = f"{test_name}_{metric}_{int(time.time())}"
        
        return DiagnosticIssue(
            id=issue_id,
            timestamp=datetime.now().isoformat(),
            severity=severity,
            category='performance',
            component=test_name,
            title=f'{description}: {metric} = {value}',
            description=f'{test_name} test shows {description.lower()}',
            symptoms=[f'{metric}: {value}'],
            root_cause=f'Performance threshold exceeded for {metric}',
            impact='System performance may be degraded',
            recommendations=self._get_performance_recommendations(metric, value),
            recovery_actions=self._get_performance_recovery_actions(metric),
            related_issues=[],
            details=details
        )
    
    def _get_performance_recommendations(self, metric: str, value: float) -> List[str]:
        """Get recommendations for performance issues"""
        recommendations = {
            'connection_time': [
                'Check network latency between containers',
                'Optimize database connection pool settings',
                'Review database query performance',
                'Check for database locks or blocking queries'
            ],
            'success_rate': [
                'Investigate failed connection attempts',
                'Check database and network stability',
                'Review error logs for patterns',
                'Verify configuration settings'
            ],
            'missing_tables': [
                'Run database initialization script',
                'Check database migration status',
                'Verify schema creation process',
                'Review database permissions'
            ]
        }
        
        return recommendations.get(metric, ['Investigate performance issue', 'Review system resources'])
    
    def _get_performance_recovery_actions(self, metric: str) -> List[str]:
        """Get recovery actions for performance issues"""
        actions = {
            'connection_time': [
                'Restart database container',
                'Clear connection pool',
                'Optimize database configuration',
                'Check system resources'
            ],
            'success_rate': [
                'Restart affected services',
                'Reset network connections',
                'Clear caches',
                'Check service dependencies'
            ],
            'missing_tables': [
                'Execute database initialization',
                'Run schema creation scripts',
                'Restore from backup if needed'
            ]
        }
        
        return actions.get(metric, ['Apply targeted fixes', 'Monitor system behavior'])
    
    def _determine_overall_health(self, issues: List[DiagnosticIssue]) -> str:
        """Determine overall system health based on issues"""
        if not issues:
            return 'healthy'
        
        critical_count = sum(1 for issue in issues if issue.severity == IssueSeverity.CRITICAL)
        high_count = sum(1 for issue in issues if issue.severity == IssueSeverity.HIGH)
        
        if critical_count > 0:
            return 'critical'
        elif high_count > 2:
            return 'degraded'
        elif high_count > 0:
            return 'warning'
        else:
            return 'minor_issues'
    
    def _generate_recommendations(self, issues: List[DiagnosticIssue], level: DiagnosticLevel) -> List[str]:
        """Generate overall recommendations based on issues"""
        recommendations = set()
        
        # Collect recommendations from all issues
        for issue in issues:
            recommendations.update(issue.recommendations)
        
        # Add level-specific recommendations
        if level == DiagnosticLevel.QUICK and issues:
            recommendations.add('Run standard diagnostic for more detailed analysis')
        elif level == DiagnosticLevel.STANDARD and any(issue.severity == IssueSeverity.CRITICAL for issue in issues):
            recommendations.add('Run comprehensive diagnostic to identify root causes')
        
        # Prioritize recommendations
        priority_recommendations = [
            'Fix critical database connectivity issues',
            'Restart failed services',
            'Initialize missing database components',
            'Optimize system performance',
            'Monitor system health'
        ]
        
        # Return prioritized list
        final_recommendations = []
        for priority_rec in priority_recommendations:
            if any(priority_rec.lower() in rec.lower() for rec in recommendations):
                final_recommendations.append(priority_rec)
        
        # Add remaining recommendations
        for rec in sorted(recommendations):
            if not any(rec.lower() in final_rec.lower() for final_rec in final_recommendations):
                final_recommendations.append(rec)
        
        return final_recommendations[:10]  # Top 10 recommendations
    
    def _generate_recovery_plan(self, issues: List[DiagnosticIssue], level: DiagnosticLevel) -> List[str]:
        """Generate step-by-step recovery plan"""
        if not issues:
            return ['System is healthy - no recovery needed']
        
        # Group issues by severity
        critical_issues = [issue for issue in issues if issue.severity == IssueSeverity.CRITICAL]
        high_issues = [issue for issue in issues if issue.severity == IssueSeverity.HIGH]
        
        recovery_plan = []
        
        # Step 1: Address critical issues first
        if critical_issues:
            recovery_plan.append('=== CRITICAL ISSUES (Fix immediately) ===')
            for i, issue in enumerate(critical_issues, 1):
                recovery_plan.append(f'{i}. {issue.title}')
                recovery_plan.extend([f'   - {action}' for action in issue.recovery_actions[:3]])
        
        # Step 2: Address high priority issues
        if high_issues:
            recovery_plan.append('=== HIGH PRIORITY ISSUES ===')
            for i, issue in enumerate(high_issues, 1):
                recovery_plan.append(f'{i}. {issue.title}')
                recovery_plan.extend([f'   - {action}' for action in issue.recovery_actions[:2]])
        
        # Step 3: General recovery steps
        recovery_plan.extend([
            '=== GENERAL RECOVERY STEPS ===',
            '1. Verify all services are running',
            '2. Check logs for additional errors',
            '3. Run diagnostic again to verify fixes',
            '4. Monitor system stability'
        ])
        
        return recovery_plan
    
    def _generate_summary(self, test_results: Dict[str, Any], issues: List[DiagnosticIssue]) -> Dict[str, Any]:
        """Generate diagnostic summary"""
        total_tests = len(test_results)
        successful_tests = sum(1 for result in test_results.values() if result.get('success', False))
        
        # Count issues by severity
        issue_counts = {
            'critical': sum(1 for issue in issues if issue.severity == IssueSeverity.CRITICAL),
            'high': sum(1 for issue in issues if issue.severity == IssueSeverity.HIGH),
            'medium': sum(1 for issue in issues if issue.severity == IssueSeverity.MEDIUM),
            'low': sum(1 for issue in issues if issue.severity == IssueSeverity.LOW)
        }
        
        # Group issues by category
        category_counts = {}
        for issue in issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1
        
        return {
            'tests_run': total_tests,
            'tests_successful': successful_tests,
            'test_success_rate': round((successful_tests / max(total_tests, 1)) * 100, 1),
            'total_issues': len(issues),
            'issues_by_severity': issue_counts,
            'issues_by_category': category_counts,
            'most_critical_issue': issues[0].title if issues else None,
            'requires_immediate_attention': issue_counts['critical'] > 0,
            'system_operational': issue_counts['critical'] == 0 and successful_tests >= total_tests * 0.8
        }
    
    def save_diagnostic_report(self, result: DiagnosticResult, filename: str = None) -> str:
        """Save diagnostic report to file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/home/user/Testing/ai-model-validation-platform/backend/logs/diagnostic_report_{timestamp}.json'
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Convert to serializable format
        report_data = {
            'timestamp': result.timestamp,
            'diagnostic_level': result.diagnostic_level.value,
            'duration_ms': result.duration_ms,
            'overall_health': result.overall_health,
            'issues_found': [asdict(issue) for issue in result.issues_found],
            'components_tested': result.components_tested,
            'test_results': result.test_results,
            'recommendations': result.recommendations,
            'recovery_plan': result.recovery_plan,
            'summary': result.summary
        }
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return filename
    
    def generate_diagnostic_report_text(self, result: DiagnosticResult) -> str:
        """Generate human-readable diagnostic report"""
        report = []
        report.append("# Database Connectivity Diagnostic Report")
        report.append(f"Generated: {result.timestamp}")
        report.append(f"Diagnostic Level: {result.diagnostic_level.value.title()}")
        report.append(f"Duration: {result.duration_ms}ms\n")
        
        # Overall status
        status_emoji = {
            'healthy': '✅',
            'minor_issues': '⚠️',
            'warning': '⚠️',
            'degraded': '🟡',
            'critical': '🚨'
        }
        
        report.append(f"## Overall Health: {status_emoji.get(result.overall_health, '❓')} {result.overall_health.upper().replace('_', ' ')}")
        report.append(f"Components Tested: {', '.join(result.components_tested)}")
        report.append(f"Test Success Rate: {result.summary['test_success_rate']}%")
        report.append(f"Issues Found: {result.summary['total_issues']}\n")
        
        # Issues summary
        if result.issues_found:
            report.append("## Issues Summary")
            issue_counts = result.summary['issues_by_severity']
            
            for severity, count in issue_counts.items():
                if count > 0:
                    emoji = {
                        'critical': '🚨',
                        'high': '🔴',
                        'medium': '🟡',
                        'low': '🟢'
                    }
                    report.append(f"- {emoji.get(severity, '❓')} {severity.title()}: {count}")
            
            report.append("")
            
            # Detailed issues
            report.append("## Detailed Issues")
            
            # Sort issues by severity
            severity_order = [IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.MEDIUM, IssueSeverity.LOW]
            sorted_issues = sorted(result.issues_found, key=lambda x: severity_order.index(x.severity))
            
            for i, issue in enumerate(sorted_issues, 1):
                severity_emoji = {
                    IssueSeverity.CRITICAL: '🚨',
                    IssueSeverity.HIGH: '🔴',
                    IssueSeverity.MEDIUM: '🟡',
                    IssueSeverity.LOW: '🟢'
                }
                
                report.append(f"### {i}. {severity_emoji.get(issue.severity, '❓')} {issue.title}")
                report.append(f"**Component:** {issue.component}")
                report.append(f"**Category:** {issue.category}")
                report.append(f"**Description:** {issue.description}")
                
                if issue.symptoms:
                    report.append(f"**Symptoms:** {', '.join(issue.symptoms)}")
                
                if issue.root_cause:
                    report.append(f"**Root Cause:** {issue.root_cause}")
                
                report.append(f"**Impact:** {issue.impact}")
                
                if issue.recommendations:
                    report.append("**Recommendations:**")
                    for rec in issue.recommendations:
                        report.append(f"  - {rec}")
                
                report.append("")
        
        # Test results summary
        report.append("## Test Results Summary")
        for test_name, test_result in result.test_results.items():
            status = '✅' if test_result.get('success', False) else '❌'
            duration = test_result.get('duration_ms', 0)
            report.append(f"- {status} {test_name}: {duration:.1f}ms")
            
            if not test_result.get('success', False) and 'error' in test_result:
                report.append(f"    Error: {test_result['error']}")
        
        report.append("")
        
        # Recommendations
        if result.recommendations:
            report.append("## 💡 Recommendations")
            for i, rec in enumerate(result.recommendations, 1):
                report.append(f"{i}. {rec}")
            report.append("")
        
        # Recovery plan
        if result.recovery_plan:
            report.append("## 🔧 Recovery Plan")
            for step in result.recovery_plan:
                if step.startswith('==='):
                    report.append(f"\n**{step.strip('= ')}**")
                else:
                    report.append(step)
        
        return "\n".join(report)

def main():
    """Main diagnostic execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Connectivity Diagnostic Toolkit')
    parser.add_argument('--level', choices=['quick', 'standard', 'comprehensive', 'deep'], 
                       default='standard', help='Diagnostic level')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--report', action='store_true', help='Generate human-readable report')
    parser.add_argument('--config', help='Custom configuration file')
    parser.add_argument('--list-tests', action='store_true', help='List available tests')
    
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
    
    # Create diagnostic toolkit
    toolkit = DiagnosticToolkit(config)
    
    if args.list_tests:
        # List available tests
        print("\n=== Available Diagnostic Tests ===")
        test_methods = toolkit._get_test_methods()
        for test_name, method in test_methods.items():
            print(f"- {test_name}: {method.__doc__ or 'No description'}")
        
        print("\n=== Diagnostic Levels ===")
        for level, config in toolkit.config['diagnostic_levels'].items():
            print(f"- {level.value}: {', '.join(config['tests'])}")
        return
    
    # Run diagnostic
    level = DiagnosticLevel(args.level)
    
    print(f"\nRunning {level.value} diagnostic...")
    
    if level == DiagnosticLevel.QUICK:
        result = toolkit.run_quick_diagnostic()
    elif level == DiagnosticLevel.STANDARD:
        result = toolkit.run_standard_diagnostic()
    elif level == DiagnosticLevel.COMPREHENSIVE:
        result = toolkit.run_comprehensive_diagnostic()
    elif level == DiagnosticLevel.DEEP:
        result = toolkit.run_deep_diagnostic()
    else:
        result = toolkit.run_standard_diagnostic()
    
    # Display summary
    print(f"\n=== Diagnostic Results ({result.diagnostic_level.value.title()}) ===")
    print(f"Overall Health: {result.overall_health.upper().replace('_', ' ')}")
    print(f"Duration: {result.duration_ms}ms")
    print(f"Components Tested: {len(result.components_tested)}")
    print(f"Issues Found: {len(result.issues_found)}")
    print(f"Test Success Rate: {result.summary['test_success_rate']}%")
    
    if result.issues_found:
        print(f"\n🚨 Issues by Severity:")
        issue_counts = result.summary['issues_by_severity']
        for severity, count in issue_counts.items():
            if count > 0:
                print(f"  {severity.title()}: {count}")
    
    if result.recommendations:
        print(f"\n💡 Top Recommendations:")
        for i, rec in enumerate(result.recommendations[:5], 1):
            print(f"  {i}. {rec}")
    
    # Save results
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'/home/user/Testing/ai-model-validation-platform/backend/logs/diagnostic_report_{timestamp}.json'
    
    saved_file = toolkit.save_diagnostic_report(result, output_file)
    print(f"\nResults saved to: {saved_file}")
    
    # Generate text report if requested
    if args.report:
        report = toolkit.generate_diagnostic_report_text(result)
        report_file = saved_file.replace('.json', '_report.md')
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"Report saved to: {report_file}")
        print(f"\n{report}")

if __name__ == '__main__':
    main()
