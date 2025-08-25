#!/usr/bin/env python3
"""
Automated Repair and Recovery Scripts

Intelligent automated repair system that can diagnose database connectivity
issues and automatically apply appropriate fixes and recovery procedures.

Features:
- Automated issue detection and classification
- Context-aware repair strategy selection
- Self-healing capabilities with safety checks
- Recovery verification and rollback
- Comprehensive logging and reporting
- Integration with all diagnostic tools
- Progressive repair escalation
"""

import os
import sys
import json
import time
import logging
import subprocess
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add backend directory to path
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')

try:
    from diagnostic_toolkit import DiagnosticToolkit, DiagnosticLevel, DiagnosticIssue
    from database_recovery_test import DatabaseRecoveryTester, RecoveryScenario
    from validate_all_tables import AllTablesValidator
    from db_health_check import PostgreSQLHealthChecker
except ImportError as e:
    print(f"Warning: Some repair modules unavailable: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RepairStrategy(Enum):
    """Repair strategy types"""
    RESTART_SERVICES = "restart_services"
    RECREATE_DATABASE = "recreate_database"
    REBUILD_CONTAINERS = "rebuild_containers"
    NETWORK_RESET = "network_reset"
    SCHEMA_REPAIR = "schema_repair"
    CONNECTION_POOL_RESET = "connection_pool_reset"
    SYSTEM_RESOURCE_CLEANUP = "system_resource_cleanup"
    COMPLETE_REBUILD = "complete_rebuild"

class RepairRisk(Enum):
    """Risk levels for repair actions"""
    LOW = "low"           # No data loss risk
    MEDIUM = "medium"     # Temporary service interruption
    HIGH = "high"         # Potential data loss or extended downtime
    CRITICAL = "critical" # Major system changes, backup required

@dataclass
class RepairAction:
    """Individual repair action"""
    name: str
    description: str
    strategy: RepairStrategy
    risk_level: RepairRisk
    estimated_time_seconds: int
    prerequisites: List[str]
    success_criteria: List[str]
    rollback_possible: bool
    execute_func: Optional[Callable] = None
    verify_func: Optional[Callable] = None

@dataclass
class RepairPlan:
    """Complete repair plan"""
    plan_id: str
    timestamp: str
    issues_addressed: List[str]
    actions: List[RepairAction]
    total_estimated_time: int
    max_risk_level: RepairRisk
    requires_approval: bool
    rollback_plan: List[str]

@dataclass
class RepairResult:
    """Repair execution result"""
    plan_id: str
    timestamp: str
    execution_successful: bool
    actions_executed: int
    actions_successful: int
    total_duration_ms: float
    issues_resolved: List[str]
    remaining_issues: List[str]
    rollback_performed: bool
    lessons_learned: List[str]
    recommendations: List[str]
    details: Dict[str, Any]

class AutomatedRepairSystem:
    """Intelligent automated repair and recovery system"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._load_default_config()
        self.diagnostic_toolkit = DiagnosticToolkit()
        self.recovery_tester = DatabaseRecoveryTester()
        self.tables_validator = AllTablesValidator()
        self.health_checker = PostgreSQLHealthChecker()
        
        self.repair_history = []
        self.available_actions = self._initialize_repair_actions()
        self.docker_compose_path = '/home/user/Testing/ai-model-validation-platform'
        
    def _load_default_config(self) -> Dict:
        """Load default repair system configuration"""
        return {
            'auto_repair_enabled': True,
            'max_repair_attempts': 3,
            'approval_required_for_risk': [RepairRisk.HIGH, RepairRisk.CRITICAL],
            'backup_before_high_risk': True,
            'rollback_on_failure': True,
            'verification_timeout_seconds': 300,
            'repair_strategies': {
                RepairStrategy.RESTART_SERVICES: {
                    'enabled': True,
                    'timeout_seconds': 120,
                    'success_threshold': 0.8
                },
                RepairStrategy.RECREATE_DATABASE: {
                    'enabled': True,
                    'timeout_seconds': 300,
                    'success_threshold': 0.9
                },
                RepairStrategy.REBUILD_CONTAINERS: {
                    'enabled': True,
                    'timeout_seconds': 600,
                    'success_threshold': 0.9
                },
                RepairStrategy.COMPLETE_REBUILD: {
                    'enabled': False,  # Requires manual approval
                    'timeout_seconds': 900,
                    'success_threshold': 1.0
                }
            },
            'issue_patterns': {
                'connection_refused': {
                    'patterns': ['connection refused', 'could not connect'],
                    'strategies': [RepairStrategy.RESTART_SERVICES, RepairStrategy.NETWORK_RESET]
                },
                'database_missing': {
                    'patterns': ['database does not exist', 'database not found'],
                    'strategies': [RepairStrategy.RECREATE_DATABASE]
                },
                'tables_missing': {
                    'patterns': ['relation does not exist', 'table not found'],
                    'strategies': [RepairStrategy.SCHEMA_REPAIR, RepairStrategy.RECREATE_DATABASE]
                },
                'container_issues': {
                    'patterns': ['container not running', 'docker', 'service unavailable'],
                    'strategies': [RepairStrategy.RESTART_SERVICES, RepairStrategy.REBUILD_CONTAINERS]
                },
                'resource_exhaustion': {
                    'patterns': ['out of memory', 'disk full', 'no space left'],
                    'strategies': [RepairStrategy.SYSTEM_RESOURCE_CLEANUP]
                }
            }
        }
    
    def _initialize_repair_actions(self) -> Dict[RepairStrategy, RepairAction]:
        """Initialize available repair actions"""
        return {
            RepairStrategy.RESTART_SERVICES: RepairAction(
                name="Restart Services",
                description="Restart PostgreSQL and backend containers",
                strategy=RepairStrategy.RESTART_SERVICES,
                risk_level=RepairRisk.LOW,
                estimated_time_seconds=60,
                prerequisites=["Docker containers exist"],
                success_criteria=["All containers running", "Database connectivity restored"],
                rollback_possible=True,
                execute_func=self._restart_services,
                verify_func=self._verify_services_running
            ),
            
            RepairStrategy.RECREATE_DATABASE: RepairAction(
                name="Recreate Database",
                description="Drop and recreate database with fresh schema",
                strategy=RepairStrategy.RECREATE_DATABASE,
                risk_level=RepairRisk.HIGH,
                estimated_time_seconds=180,
                prerequisites=["PostgreSQL container running", "Database connection available"],
                success_criteria=["Database exists", "All tables created", "Schema valid"],
                rollback_possible=False,  # Cannot rollback database recreation
                execute_func=self._recreate_database,
                verify_func=self._verify_database_schema
            ),
            
            RepairStrategy.REBUILD_CONTAINERS: RepairAction(
                name="Rebuild Containers",
                description="Stop, rebuild, and restart all Docker containers",
                strategy=RepairStrategy.REBUILD_CONTAINERS,
                risk_level=RepairRisk.MEDIUM,
                estimated_time_seconds=300,
                prerequisites=["Docker daemon running", "Docker Compose files available"],
                success_criteria=["All containers rebuilt", "All services running", "Database accessible"],
                rollback_possible=True,
                execute_func=self._rebuild_containers,
                verify_func=self._verify_containers_rebuilt
            ),
            
            RepairStrategy.NETWORK_RESET: RepairAction(
                name="Network Reset",
                description="Reset Docker network and container networking",
                strategy=RepairStrategy.NETWORK_RESET,
                risk_level=RepairRisk.LOW,
                estimated_time_seconds=30,
                prerequisites=["Docker daemon running"],
                success_criteria=["Network connectivity restored", "Container DNS working"],
                rollback_possible=True,
                execute_func=self._reset_network,
                verify_func=self._verify_network_connectivity
            ),
            
            RepairStrategy.SCHEMA_REPAIR: RepairAction(
                name="Schema Repair",
                description="Repair database schema by creating missing tables and indexes",
                strategy=RepairStrategy.SCHEMA_REPAIR,
                risk_level=RepairRisk.LOW,
                estimated_time_seconds=90,
                prerequisites=["Database connection available"],
                success_criteria=["All tables exist", "Indexes created", "Constraints valid"],
                rollback_possible=True,
                execute_func=self._repair_schema,
                verify_func=self._verify_schema_repair
            ),
            
            RepairStrategy.CONNECTION_POOL_RESET: RepairAction(
                name="Connection Pool Reset",
                description="Reset database connection pool and clear cached connections",
                strategy=RepairStrategy.CONNECTION_POOL_RESET,
                risk_level=RepairRisk.LOW,
                estimated_time_seconds=15,
                prerequisites=["Backend service running"],
                success_criteria=["Connection pool cleared", "New connections working"],
                rollback_possible=True,
                execute_func=self._reset_connection_pool,
                verify_func=self._verify_connection_pool
            ),
            
            RepairStrategy.SYSTEM_RESOURCE_CLEANUP: RepairAction(
                name="System Resource Cleanup",
                description="Clean up disk space, memory, and other system resources",
                strategy=RepairStrategy.SYSTEM_RESOURCE_CLEANUP,
                risk_level=RepairRisk.LOW,
                estimated_time_seconds=120,
                prerequisites=["System access available"],
                success_criteria=["Disk space available", "Memory usage normal"],
                rollback_possible=False,
                execute_func=self._cleanup_system_resources,
                verify_func=self._verify_system_resources
            ),
            
            RepairStrategy.COMPLETE_REBUILD: RepairAction(
                name="Complete System Rebuild",
                description="Complete rebuild of all containers, networks, and databases",
                strategy=RepairStrategy.COMPLETE_REBUILD,
                risk_level=RepairRisk.CRITICAL,
                estimated_time_seconds=600,
                prerequisites=["Full system backup available"],
                success_criteria=["All systems operational", "All data restored", "Full functionality verified"],
                rollback_possible=True,  # From backup
                execute_func=self._complete_rebuild,
                verify_func=self._verify_complete_system
            )
        }
    
    def analyze_and_generate_repair_plan(self, diagnostic_level: DiagnosticLevel = DiagnosticLevel.STANDARD) -> RepairPlan:
        """Analyze system and generate intelligent repair plan"""
        logger.info(f"Analyzing system to generate repair plan (level: {diagnostic_level.value})...")
        
        # Run comprehensive diagnostic
        diagnostic_result = self.diagnostic_toolkit._run_diagnostic(diagnostic_level)
        
        # Classify issues and determine repair strategies
        repair_strategies = self._classify_issues_and_strategies(diagnostic_result.issues_found)
        
        # Generate repair actions based on strategies
        repair_actions = self._generate_repair_actions(repair_strategies, diagnostic_result)
        
        # Create repair plan
        plan_id = f"repair_{int(time.time())}"
        total_time = sum(action.estimated_time_seconds for action in repair_actions)
        max_risk = max([action.risk_level for action in repair_actions], default=RepairRisk.LOW)
        requires_approval = max_risk in self.config['approval_required_for_risk']
        
        plan = RepairPlan(
            plan_id=plan_id,
            timestamp=datetime.now().isoformat(),
            issues_addressed=[issue.title for issue in diagnostic_result.issues_found],
            actions=repair_actions,
            total_estimated_time=total_time,
            max_risk_level=max_risk,
            requires_approval=requires_approval,
            rollback_plan=self._generate_rollback_plan(repair_actions)
        )
        
        logger.info(f"Generated repair plan {plan_id} with {len(repair_actions)} actions (risk: {max_risk.value})")
        
        return plan
    
    def _classify_issues_and_strategies(self, issues: List[DiagnosticIssue]) -> Dict[str, List[RepairStrategy]]:
        """Classify issues and determine appropriate repair strategies"""
        issue_classifications = {}
        
        for issue in issues:
            # Analyze issue text to match patterns
            issue_text = f"{issue.title} {issue.description} {' '.join(issue.symptoms)}".lower()
            
            matched_strategies = []
            
            # Check against known issue patterns
            for issue_type, pattern_info in self.config['issue_patterns'].items():
                for pattern in pattern_info['patterns']:
                    if pattern.lower() in issue_text:
                        matched_strategies.extend(pattern_info['strategies'])
                        break
            
            # Fallback classification based on issue category and severity
            if not matched_strategies:
                matched_strategies = self._fallback_strategy_classification(issue)
            
            issue_classifications[issue.id] = {
                'issue': issue,
                'strategies': list(set(matched_strategies))  # Remove duplicates
            }
        
        return issue_classifications
    
    def _fallback_strategy_classification(self, issue: DiagnosticIssue) -> List[RepairStrategy]:
        """Fallback strategy classification when no patterns match"""
        # Based on issue category and severity
        if issue.category == 'test_failure':
            if 'connection' in issue.component:
                return [RepairStrategy.RESTART_SERVICES, RepairStrategy.CONNECTION_POOL_RESET]
            elif 'schema' in issue.component:
                return [RepairStrategy.SCHEMA_REPAIR]
            elif 'container' in issue.component:
                return [RepairStrategy.RESTART_SERVICES]
            else:
                return [RepairStrategy.RESTART_SERVICES]
        
        elif issue.category == 'performance':
            return [RepairStrategy.CONNECTION_POOL_RESET, RepairStrategy.SYSTEM_RESOURCE_CLEANUP]
        
        else:
            # Generic repair strategies
            if issue.severity.value in ['critical', 'high']:
                return [RepairStrategy.RESTART_SERVICES, RepairStrategy.RECREATE_DATABASE]
            else:
                return [RepairStrategy.CONNECTION_POOL_RESET]
    
    def _generate_repair_actions(self, issue_classifications: Dict, diagnostic_result) -> List[RepairAction]:
        """Generate ordered list of repair actions"""
        # Collect all unique strategies with their priorities
        strategy_priorities = {}
        
        for issue_id, classification in issue_classifications.items():
            issue = classification['issue']
            strategies = classification['strategies']
            
            # Weight strategies by issue severity
            severity_weight = {
                'critical': 10,
                'high': 8,
                'medium': 5,
                'low': 2
            }.get(issue.severity.value, 1)
            
            for strategy in strategies:
                if strategy not in strategy_priorities:
                    strategy_priorities[strategy] = 0
                strategy_priorities[strategy] += severity_weight
        
        # Sort strategies by priority and risk (low risk first)
        sorted_strategies = sorted(
            strategy_priorities.items(),
            key=lambda x: (x[1], -x[0].value.count('_')),  # Priority, then simple strategies first
            reverse=True
        )
        
        # Generate repair actions, avoiding redundancy
        repair_actions = []
        used_strategies = set()
        
        for strategy, priority in sorted_strategies:
            if strategy in used_strategies:
                continue
                
            if strategy in self.available_actions:
                action = self.available_actions[strategy]
                
                # Check if strategy is enabled
                if self.config['repair_strategies'].get(strategy, {}).get('enabled', True):
                    repair_actions.append(action)
                    used_strategies.add(strategy)
                    
                    # Skip higher risk actions if lower risk might work
                    if action.risk_level == RepairRisk.LOW and len(repair_actions) >= 2:
                        break
        
        # Ensure we have at least one repair action
        if not repair_actions:
            repair_actions.append(self.available_actions[RepairStrategy.RESTART_SERVICES])
        
        return repair_actions
    
    def _generate_rollback_plan(self, repair_actions: List[RepairAction]) -> List[str]:
        """Generate rollback plan for repair actions"""
        rollback_steps = []
        
        # Reverse order rollback
        for action in reversed(repair_actions):
            if action.rollback_possible:
                rollback_steps.append(f"Rollback {action.name}: {action.description}")
            else:
                rollback_steps.append(f"Cannot rollback {action.name} - manual intervention required")
        
        rollback_steps.extend([
            "Verify system state after rollback",
            "Run diagnostic to assess remaining issues",
            "Consider alternative repair strategies"
        ])
        
        return rollback_steps
    
    def execute_repair_plan(self, plan: RepairPlan, auto_approve: bool = False) -> RepairResult:
        """Execute repair plan with safety checks and verification"""
        logger.info(f"Starting execution of repair plan {plan.plan_id}...")
        start_time = time.time()
        
        # Check if approval is required
        if plan.requires_approval and not auto_approve:
            logger.warning(f"Repair plan requires manual approval (risk: {plan.max_risk_level.value})")
            return RepairResult(
                plan_id=plan.plan_id,
                timestamp=datetime.now().isoformat(),
                execution_successful=False,
                actions_executed=0,
                actions_successful=0,
                total_duration_ms=0,
                issues_resolved=[],
                remaining_issues=plan.issues_addressed,
                rollback_performed=False,
                lessons_learned=["Manual approval required for high-risk repairs"],
                recommendations=["Review repair plan and approve if acceptable"],
                details={'approval_required': True, 'max_risk': plan.max_risk_level.value}
            )
        
        # Create backup if required for high-risk operations
        backup_created = False
        if (plan.max_risk_level in [RepairRisk.HIGH, RepairRisk.CRITICAL] and 
            self.config['backup_before_high_risk']):
            backup_created = self._create_system_backup()
            if not backup_created:
                logger.error("Failed to create backup before high-risk repair")
                return self._create_failed_result(plan, "Backup creation failed")
        
        # Execute repair actions
        actions_executed = 0
        actions_successful = 0
        execution_details = {}
        rollback_performed = False
        
        try:
            for i, action in enumerate(plan.actions):
                logger.info(f"Executing action {i+1}/{len(plan.actions)}: {action.name}")
                
                # Check prerequisites
                if not self._check_prerequisites(action):
                    logger.error(f"Prerequisites not met for {action.name}")
                    execution_details[action.name] = {
                        'executed': False,
                        'error': 'Prerequisites not met'
                    }
                    break
                
                actions_executed += 1
                
                # Execute action
                action_start = time.time()
                try:
                    if action.execute_func:
                        result = action.execute_func()
                        action_duration = (time.time() - action_start) * 1000
                        
                        # Verify action success
                        verification_successful = True
                        if action.verify_func:
                            verification_successful = action.verify_func()
                        
                        if result and verification_successful:
                            actions_successful += 1
                            execution_details[action.name] = {
                                'executed': True,
                                'successful': True,
                                'duration_ms': round(action_duration, 2),
                                'details': result if isinstance(result, dict) else {'result': result}
                            }
                            logger.info(f"✅ {action.name} completed successfully")
                        else:
                            execution_details[action.name] = {
                                'executed': True,
                                'successful': False,
                                'duration_ms': round(action_duration, 2),
                                'error': 'Verification failed' if not verification_successful else 'Execution failed'
                            }
                            logger.error(f"❌ {action.name} failed")
                            
                            # Consider rollback on failure
                            if self.config['rollback_on_failure'] and backup_created:
                                logger.info("Performing rollback due to action failure...")
                                rollback_performed = self._perform_rollback(plan, backup_created)
                                break
                    else:
                        logger.warning(f"No execute function available for {action.name}")
                        execution_details[action.name] = {
                            'executed': False,
                            'error': 'No execute function available'
                        }
                
                except Exception as e:
                    action_duration = (time.time() - action_start) * 1000
                    logger.error(f"Action {action.name} crashed: {e}")
                    execution_details[action.name] = {
                        'executed': True,
                        'successful': False,
                        'duration_ms': round(action_duration, 2),
                        'error': str(e),
                        'traceback': traceback.format_exc()
                    }
                    
                    # Consider rollback on crash
                    if self.config['rollback_on_failure'] and backup_created:
                        logger.info("Performing rollback due to action crash...")
                        rollback_performed = self._perform_rollback(plan, backup_created)
                        break
        
        except Exception as e:
            logger.error(f"Repair plan execution crashed: {e}")
            execution_details['execution_error'] = str(e)
        
        # Post-execution verification
        post_execution_diagnostic = self.diagnostic_toolkit.run_quick_diagnostic()
        remaining_issues = [issue.title for issue in post_execution_diagnostic.issues_found]
        issues_resolved = [issue for issue in plan.issues_addressed if issue not in remaining_issues]
        
        # Generate lessons learned
        lessons_learned = self._generate_execution_lessons(plan, actions_executed, actions_successful, execution_details)
        
        # Generate recommendations
        recommendations = self._generate_execution_recommendations(plan, actions_successful, len(plan.actions), remaining_issues)
        
        total_duration = (time.time() - start_time) * 1000
        execution_successful = actions_successful > 0 and len(remaining_issues) < len(plan.issues_addressed)
        
        result = RepairResult(
            plan_id=plan.plan_id,
            timestamp=datetime.now().isoformat(),
            execution_successful=execution_successful,
            actions_executed=actions_executed,
            actions_successful=actions_successful,
            total_duration_ms=round(total_duration, 2),
            issues_resolved=issues_resolved,
            remaining_issues=remaining_issues,
            rollback_performed=rollback_performed,
            lessons_learned=lessons_learned,
            recommendations=recommendations,
            details={
                'backup_created': backup_created,
                'max_risk_level': plan.max_risk_level.value,
                'execution_details': execution_details,
                'post_execution_health': post_execution_diagnostic.overall_health
            }
        )
        
        self.repair_history.append(result)
        
        logger.info(f"Repair plan execution completed: {actions_successful}/{actions_executed} actions successful")
        
        return result
    
    def _create_failed_result(self, plan: RepairPlan, error: str) -> RepairResult:
        """Create failed repair result"""
        return RepairResult(
            plan_id=plan.plan_id,
            timestamp=datetime.now().isoformat(),
            execution_successful=False,
            actions_executed=0,
            actions_successful=0,
            total_duration_ms=0,
            issues_resolved=[],
            remaining_issues=plan.issues_addressed,
            rollback_performed=False,
            lessons_learned=[f"Repair failed: {error}"],
            recommendations=["Investigate failure cause", "Consider manual intervention"],
            details={'execution_error': error}
        )
    
    def _create_system_backup(self) -> bool:
        """Create system backup before high-risk operations"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = '/home/user/Testing/ai-model-validation-platform/backend/backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create database dump
            backup_file = f"{backup_dir}/pre_repair_backup_{timestamp}.sql"
            
            result = subprocess.run([
                'docker-compose', 'exec', '-T', 'postgres',
                'pg_dump', '-U', 'postgres', 'vru_validation'
            ], 
            cwd=self.docker_compose_path,
            capture_output=True,
            text=True,
            timeout=120
            )
            
            if result.returncode == 0:
                with open(backup_file, 'w') as f:
                    f.write(result.stdout)
                
                logger.info(f"System backup created: {backup_file}")
                return True
            else:
                logger.error(f"Backup creation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Backup creation error: {e}")
            return False
    
    def _check_prerequisites(self, action: RepairAction) -> bool:
        """Check if action prerequisites are met"""
        # This is a simplified check - in practice, you'd implement specific checks
        for prereq in action.prerequisites:
            if "Docker" in prereq:
                # Check if Docker is running
                try:
                    subprocess.run(['docker', 'version'], capture_output=True, check=True, timeout=10)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    return False
        
        return True
    
    def _perform_rollback(self, plan: RepairPlan, backup_available: bool) -> bool:
        """Perform rollback of repair actions"""
        try:
            logger.info("Starting rollback procedure...")
            
            # Simple rollback - restart all services
            restart_result = subprocess.run(
                ['docker-compose', 'restart'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if restart_result.returncode == 0:
                logger.info("Rollback completed successfully")
                return True
            else:
                logger.error(f"Rollback failed: {restart_result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Rollback error: {e}")
            return False
    
    def _generate_execution_lessons(self, plan: RepairPlan, executed: int, successful: int, details: Dict) -> List[str]:
        """Generate lessons learned from repair execution"""
        lessons = []
        
        success_rate = (successful / max(executed, 1)) * 100
        
        if success_rate == 100:
            lessons.append("All repair actions completed successfully")
        elif success_rate >= 50:
            lessons.append(f"Partial success: {successful}/{executed} actions completed")
        else:
            lessons.append(f"Low success rate: only {successful}/{executed} actions completed")
        
        # Action-specific lessons
        for action_name, action_details in details.items():
            if isinstance(action_details, dict) and not action_details.get('successful', True):
                error = action_details.get('error', 'Unknown error')
                lessons.append(f"Action '{action_name}' failed: {error}")
        
        return lessons
    
    def _generate_execution_recommendations(self, plan: RepairPlan, successful: int, total: int, remaining_issues: List[str]) -> List[str]:
        """Generate recommendations based on execution results"""
        recommendations = []
        
        if successful == total and not remaining_issues:
            recommendations.append("All repairs successful - monitor system stability")
        elif successful < total:
            recommendations.append("Some repairs failed - investigate failed actions")
            recommendations.append("Consider alternative repair strategies")
        
        if remaining_issues:
            recommendations.append(f"Address remaining issues: {len(remaining_issues)} unresolved")
            recommendations.append("Run comprehensive diagnostic for remaining issues")
        
        recommendations.extend([
            "Document repair results for future reference",
            "Schedule follow-up monitoring",
            "Review and update repair procedures based on lessons learned"
        ])
        
        return recommendations
    
    # Repair action implementations
    def _restart_services(self) -> Dict[str, Any]:
        """Restart PostgreSQL and backend services"""
        try:
            result = subprocess.run(
                ['docker-compose', 'restart', 'postgres', 'backend'],
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
    
    def _verify_services_running(self) -> bool:
        """Verify that services are running properly"""
        try:
            # Use health checker to verify
            health_results = self.health_checker.run_comprehensive_health_check()
            summary = self.health_checker.get_health_summary(health_results)
            return summary['overall_status'] in ['healthy', 'degraded']
        except Exception:
            return False
    
    def _recreate_database(self) -> Dict[str, Any]:
        """Recreate database with fresh schema"""
        try:
            # This is a placeholder - implement actual database recreation
            from database_init_verifier import DatabaseInitializationVerifier
            
            verifier = DatabaseInitializationVerifier()
            result = verifier.initialize_database_schema()
            
            return {
                'success': result['success'],
                'details': result
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_database_schema(self) -> bool:
        """Verify database schema is correct"""
        try:
            validator_result = self.tables_validator.validate_all_tables()
            return validator_result.validation_successful
        except Exception:
            return False
    
    def _rebuild_containers(self) -> Dict[str, Any]:
        """Rebuild all Docker containers"""
        try:
            # Stop containers
            stop_result = subprocess.run(
                ['docker-compose', 'down'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if stop_result.returncode != 0:
                return {'success': False, 'error': f'Stop failed: {stop_result.stderr}'}
            
            # Rebuild and start
            build_result = subprocess.run(
                ['docker-compose', 'up', '-d', '--build'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            return {
                'success': build_result.returncode == 0,
                'stdout': build_result.stdout,
                'stderr': build_result.stderr
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_containers_rebuilt(self) -> bool:
        """Verify containers are rebuilt and running"""
        try:
            result = subprocess.run(
                ['docker-compose', 'ps'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0 and 'Up' in result.stdout
        except Exception:
            return False
    
    def _reset_network(self) -> Dict[str, Any]:
        """Reset Docker network"""
        try:
            # Restart Docker network
            result = subprocess.run(
                ['docker-compose', 'down'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            time.sleep(5)
            
            result2 = subprocess.run(
                ['docker-compose', 'up', '-d'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return {
                'success': result.returncode == 0 and result2.returncode == 0,
                'details': {'down': result.stderr, 'up': result2.stderr}
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_network_connectivity(self) -> bool:
        """Verify network connectivity is working"""
        try:
            # Simple connectivity check
            from network_connectivity_test import NetworkConnectivityTester
            tester = NetworkConnectivityTester()
            result = tester.test_service_health('postgres')
            return result.success
        except Exception:
            return False
    
    def _repair_schema(self) -> Dict[str, Any]:
        """Repair database schema"""
        try:
            from database_init_verifier import DatabaseInitializationVerifier
            verifier = DatabaseInitializationVerifier()
            result = verifier.initialize_database_schema()
            return {'success': result['success'], 'details': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_schema_repair(self) -> bool:
        """Verify schema repair was successful"""
        return self._verify_database_schema()
    
    def _reset_connection_pool(self) -> Dict[str, Any]:
        """Reset database connection pool"""
        try:
            # Restart backend to reset connection pool
            result = subprocess.run(
                ['docker-compose', 'restart', 'backend'],
                cwd=self.docker_compose_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {'success': result.returncode == 0}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_connection_pool(self) -> bool:
        """Verify connection pool is working"""
        try:
            from database_connection_validator import DatabaseConnectionValidator
            validator = DatabaseConnectionValidator()
            result = validator.test_connection_pool_performance()
            return result.success
        except Exception:
            return False
    
    def _cleanup_system_resources(self) -> Dict[str, Any]:
        """Clean up system resources"""
        try:
            cleanup_results = {}
            
            # Docker cleanup
            docker_result = subprocess.run(
                ['docker', 'system', 'prune', '-f'],
                capture_output=True,
                text=True,
                timeout=60
            )
            cleanup_results['docker_prune'] = docker_result.returncode == 0
            
            # Log cleanup (if logs directory exists)
            logs_dir = '/home/user/Testing/ai-model-validation-platform/backend/logs'
            if os.path.exists(logs_dir):
                # Remove old log files
                import glob
                old_logs = glob.glob(os.path.join(logs_dir, '*_2024*'))  # Remove 2024 logs
                for log_file in old_logs:
                    try:
                        os.remove(log_file)
                        cleanup_results['logs_cleaned'] = True
                    except:
                        pass
            
            return {
                'success': cleanup_results.get('docker_prune', False),
                'details': cleanup_results
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_system_resources(self) -> bool:
        """Verify system resources are adequate"""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Check if resources are within acceptable limits
            memory_ok = memory.percent < 90
            disk_ok = (disk.used / disk.total) < 0.90
            
            return memory_ok and disk_ok
        except Exception:
            return False
    
    def _complete_rebuild(self) -> Dict[str, Any]:
        """Complete system rebuild"""
        try:
            # This is a placeholder for complete rebuild
            recovery_tester = DatabaseRecoveryTester()
            result = recovery_tester.execute_complete_rebuild_scenario()
            
            return {
                'success': result.recovery_successful,
                'details': asdict(result)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_complete_system(self) -> bool:
        """Verify complete system is operational"""
        try:
            # Run comprehensive diagnostic
            diagnostic_result = self.diagnostic_toolkit.run_comprehensive_diagnostic()
            return diagnostic_result.overall_health == 'healthy'
        except Exception:
            return False
    
    def auto_repair(self, diagnostic_level: DiagnosticLevel = DiagnosticLevel.STANDARD, 
                   max_attempts: int = None) -> List[RepairResult]:
        """Fully automated repair with multiple attempts"""
        max_attempts = max_attempts or self.config['max_repair_attempts']
        repair_results = []
        
        for attempt in range(max_attempts):
            logger.info(f"Auto-repair attempt {attempt + 1}/{max_attempts}")
            
            # Generate repair plan
            plan = self.analyze_and_generate_repair_plan(diagnostic_level)
            
            # Execute plan with auto-approval for low and medium risk
            auto_approve = plan.max_risk_level not in [RepairRisk.HIGH, RepairRisk.CRITICAL]
            result = self.execute_repair_plan(plan, auto_approve=auto_approve)
            repair_results.append(result)
            
            # Check if repair was successful
            if result.execution_successful and not result.remaining_issues:
                logger.info(f"Auto-repair successful on attempt {attempt + 1}")
                break
            
            # Wait before next attempt
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 30  # Increasing wait time
                logger.info(f"Waiting {wait_time}s before next repair attempt...")
                time.sleep(wait_time)
        
        return repair_results
    
    def save_repair_report(self, results: List[RepairResult], filename: str = None) -> str:
        """Save repair results to file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/home/user/Testing/ai-model-validation-platform/backend/logs/repair_report_{timestamp}.json'
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        report_data = {
            'report_timestamp': datetime.now().isoformat(),
            'total_repair_attempts': len(results),
            'successful_repairs': sum(1 for r in results if r.execution_successful),
            'repair_results': [asdict(result) for result in results]
        }
        
        with open(filename, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return filename

def main():
    """Main automated repair execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Database Repair System')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze and generate repair plan')
    parser.add_argument('--execute', help='Execute specific repair plan JSON file')
    parser.add_argument('--auto-repair', action='store_true', help='Run fully automated repair')
    parser.add_argument('--diagnostic-level', choices=['quick', 'standard', 'comprehensive'], 
                       default='standard', help='Diagnostic depth level')
    parser.add_argument('--max-attempts', type=int, default=3, help='Maximum repair attempts')
    parser.add_argument('--auto-approve', action='store_true', help='Auto-approve all repairs (dangerous)')
    parser.add_argument('--output', help='Output file for results')
    
    args = parser.parse_args()
    
    # Create repair system
    repair_system = AutomatedRepairSystem()
    
    diagnostic_level = DiagnosticLevel(args.diagnostic_level)
    
    if args.analyze_only:
        # Generate and display repair plan only
        print("Analyzing system and generating repair plan...")
        plan = repair_system.analyze_and_generate_repair_plan(diagnostic_level)
        
        print(f"\n=== Repair Plan {plan.plan_id} ===")
        print(f"Issues to Address: {len(plan.issues_addressed)}")
        print(f"Repair Actions: {len(plan.actions)}")
        print(f"Estimated Time: {plan.total_estimated_time} seconds")
        print(f"Max Risk Level: {plan.max_risk_level.value}")
        print(f"Requires Approval: {plan.requires_approval}")
        
        print(f"\nPlanned Actions:")
        for i, action in enumerate(plan.actions, 1):
            print(f"  {i}. {action.name} (Risk: {action.risk_level.value}, Time: {action.estimated_time_seconds}s)")
            print(f"     {action.description}")
        
        if plan.issues_addressed:
            print(f"\nIssues to be addressed:")
            for issue in plan.issues_addressed:
                print(f"  - {issue}")
    
    elif args.auto_repair:
        # Run fully automated repair
        print(f"Starting automated repair (level: {diagnostic_level.value}, max attempts: {args.max_attempts})...")
        results = repair_system.auto_repair(diagnostic_level, args.max_attempts)
        
        # Display results
        successful = sum(1 for r in results if r.execution_successful)
        print(f"\n=== Automated Repair Results ===")
        print(f"Repair Attempts: {len(results)}")
        print(f"Successful: {successful}/{len(results)}")
        
        for i, result in enumerate(results, 1):
            status = '✅' if result.execution_successful else '❌'
            print(f"{status} Attempt {i}: {result.actions_successful}/{result.actions_executed} actions successful")
            print(f"   Duration: {result.total_duration_ms/1000:.1f}s")
            print(f"   Issues Resolved: {len(result.issues_resolved)}")
            print(f"   Remaining Issues: {len(result.remaining_issues)}")
        
        # Save results
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'/home/user/Testing/ai-model-validation-platform/backend/logs/auto_repair_{timestamp}.json'
        
        saved_file = repair_system.save_repair_report(results, output_file)
        print(f"\nResults saved to: {saved_file}")
    
    else:
        # Interactive repair plan generation and execution
        print("Generating repair plan...")
        plan = repair_system.analyze_and_generate_repair_plan(diagnostic_level)
        
        print(f"\n=== Generated Repair Plan ===")
        print(f"Plan ID: {plan.plan_id}")
        print(f"Issues: {len(plan.issues_addressed)}")
        print(f"Actions: {len(plan.actions)}")
        print(f"Estimated Time: {plan.total_estimated_time}s")
        print(f"Max Risk: {plan.max_risk_level.value}")
        print(f"Requires Approval: {plan.requires_approval}")
        
        # Show actions
        for i, action in enumerate(plan.actions, 1):
            risk_emoji = {
                RepairRisk.LOW: '✅',
                RepairRisk.MEDIUM: '⚠️',
                RepairRisk.HIGH: '🟠',
                RepairRisk.CRITICAL: '🚨'
            }
            print(f"  {i}. {risk_emoji.get(action.risk_level, '❓')} {action.name} ({action.estimated_time_seconds}s)")
        
        # Execute if approved
        if args.auto_approve or not plan.requires_approval:
            print("\nExecuting repair plan...")
            result = repair_system.execute_repair_plan(plan, auto_approve=args.auto_approve)
            
            status = '✅ SUCCESS' if result.execution_successful else '❌ FAILED'
            print(f"\n=== Repair Execution Result: {status} ===")
            print(f"Actions Executed: {result.actions_executed}/{len(plan.actions)}")
            print(f"Actions Successful: {result.actions_successful}")
            print(f"Duration: {result.total_duration_ms/1000:.1f}s")
            print(f"Issues Resolved: {len(result.issues_resolved)}")
            print(f"Remaining Issues: {len(result.remaining_issues)}")
            
            if result.rollback_performed:
                print(f"⚠️  Rollback was performed due to failures")
            
            if result.recommendations:
                print(f"\n💡 Recommendations:")
                for rec in result.recommendations[:5]:
                    print(f"  - {rec}")
        
        else:
            print(f"\n⚠️  Manual approval required for this repair plan (risk: {plan.max_risk_level.value})")
            print("Use --auto-approve to override (dangerous for high-risk operations)")

if __name__ == '__main__':
    main()
