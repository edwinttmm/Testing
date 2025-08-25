#!/usr/bin/env python3
"""
Master Database Validation Test Runner
Orchestrates all database connectivity and validation tests in proper sequence.
"""

import asyncio
import sys
import os
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import argparse

# Add the backend directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@dataclass
class ValidationResult:
    """Result of a validation step"""
    test_name: str
    status: str  # 'passed', 'failed', 'skipped', 'error'
    duration: float
    message: str
    details: Dict[str, Any] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.details is None:
            self.details = {}

@dataclass
class ValidationSuite:
    """Complete validation suite results"""
    suite_name: str = "Database Connectivity Validation"
    start_time: str = None
    end_time: str = None
    duration: float = 0.0
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    results: List[ValidationResult] = None
    overall_status: str = "unknown"
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now().isoformat()
        if self.results is None:
            self.results = []

class MasterValidationRunner:
    """Orchestrates all database validation tests"""
    
    def __init__(self, verbose: bool = False, repair_mode: bool = False):
        self.verbose = verbose
        self.repair_mode = repair_mode
        self.logger = self._setup_logging()
        self.validation_suite = ValidationSuite()
        
        # Test execution order (dependencies managed)
        self.test_sequence = [
            {
                'name': 'PostgreSQL Health Check',
                'module': 'db_health_check',
                'class': 'PostgreSQLHealthChecker',
                'method': 'run_comprehensive_health_check',
                'critical': True,
                'description': 'Verify PostgreSQL container health and readiness'
            },
            {
                'name': 'Network Connectivity Test',
                'module': 'network_connectivity_test',
                'class': 'NetworkConnectivityTester',
                'method': 'run_comprehensive_test',
                'critical': True,
                'description': 'Test network connectivity between containers'
            },
            {
                'name': 'Database Connection Validation',
                'module': 'database_connection_validator',
                'class': 'DatabaseConnectionValidator',
                'method': 'run_comprehensive_validation',
                'critical': True,
                'description': 'Validate database connections from backend'
            },
            {
                'name': 'Database Initialization Verification',
                'module': 'database_init_verifier',
                'class': 'DatabaseInitializationVerifier',
                'method': 'run_comprehensive_verification',
                'critical': True,
                'description': 'Verify database initialization and schema'
            },
            {
                'name': 'Table Creation Testing',
                'module': 'table_creation_tester',
                'class': 'TableCreationTester',
                'method': 'run_comprehensive_test',
                'critical': True,
                'description': 'Test complete database table creation process'
            },
            {
                'name': 'All Tables Validation',
                'module': 'validate_all_tables',
                'class': 'AllTablesValidator',
                'method': 'run_comprehensive_validation',
                'critical': True,
                'description': 'Validate all 11 database tables'
            },
            {
                'name': 'Database Recovery Testing',
                'module': 'database_recovery_test',
                'class': 'DatabaseRecoveryTester',
                'method': 'run_comprehensive_recovery_test',
                'critical': False,
                'description': 'Test database recovery scenarios'
            },
            {
                'name': 'Continuous Health Monitor Setup',
                'module': 'continuous_health_monitor',
                'class': 'ContinuousHealthMonitor',
                'method': 'run_health_check',
                'critical': False,
                'description': 'Setup continuous health monitoring'
            },
            {
                'name': 'Diagnostic Toolkit Verification',
                'module': 'diagnostic_toolkit',
                'class': 'DiagnosticToolkit',
                'method': 'run_comprehensive_diagnostic',
                'critical': False,
                'description': 'Verify diagnostic toolkit functionality'
            }
        ]
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('master_validation')
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def run_single_test(self, test_config: Dict[str, Any]) -> ValidationResult:
        """Run a single validation test"""
        test_name = test_config['name']
        self.logger.info(f"Starting test: {test_name}")
        
        start_time = datetime.now()
        
        try:
            # Dynamic import of test module
            module_name = test_config['module']
            class_name = test_config['class']
            method_name = test_config['method']
            
            # Import the module
            module = __import__(module_name, fromlist=[class_name])
            test_class = getattr(module, class_name)
            
            # Create instance and run test
            test_instance = test_class()
            test_method = getattr(test_instance, method_name)
            
            # Execute the test method
            if asyncio.iscoroutinefunction(test_method):
                result = await test_method()
            else:
                result = test_method()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Analyze result based on return type
            if hasattr(result, 'overall_health_status'):
                # Health check result
                status = 'passed' if result.overall_health_status == 'healthy' else 'failed'
                message = f"Health Status: {result.overall_health_status}"
                details = asdict(result) if hasattr(result, '__dict__') else {'result': str(result)}
            elif hasattr(result, 'overall_status'):
                # General test result
                status = 'passed' if result.overall_status == 'passed' else 'failed'
                message = f"Test Status: {result.overall_status}"
                details = asdict(result) if hasattr(result, '__dict__') else {'result': str(result)}
            elif isinstance(result, bool):
                status = 'passed' if result else 'failed'
                message = f"Test {'passed' if result else 'failed'}"
                details = {'boolean_result': result}
            elif isinstance(result, dict):
                status = 'passed' if result.get('success', False) else 'failed'
                message = result.get('message', 'Test completed')
                details = result
            else:
                # Assume passed if no exception and got result
                status = 'passed'
                message = "Test completed successfully"
                details = {'result': str(result)}
            
            self.logger.info(f"Test {test_name} completed: {status}")
            
            return ValidationResult(
                test_name=test_name,
                status=status,
                duration=duration,
                message=message,
                details=details
            )
            
        except ImportError as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Import error for {test_name}: {e}")
            return ValidationResult(
                test_name=test_name,
                status='error',
                duration=duration,
                message=f"Import error: {e}",
                details={'error_type': 'ImportError', 'error': str(e)}
            )
            
        except AttributeError as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Method not found for {test_name}: {e}")
            return ValidationResult(
                test_name=test_name,
                status='error',
                duration=duration,
                message=f"Method not found: {e}",
                details={'error_type': 'AttributeError', 'error': str(e)}
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Test {test_name} failed with exception: {e}")
            return ValidationResult(
                test_name=test_name,
                status='error',
                duration=duration,
                message=f"Test error: {e}",
                details={'error_type': type(e).__name__, 'error': str(e)}
            )
    
    async def run_validation_suite(self) -> ValidationSuite:
        """Run the complete validation suite"""
        self.logger.info("Starting Master Database Validation Suite")
        self.validation_suite.start_time = datetime.now().isoformat()
        suite_start = datetime.now()
        
        # Run tests in sequence (some may have dependencies)
        for test_config in self.test_sequence:
            result = await self.run_single_test(test_config)
            self.validation_suite.results.append(result)
            
            # Update counters
            self.validation_suite.total_tests += 1
            if result.status == 'passed':
                self.validation_suite.passed_tests += 1
            elif result.status == 'failed':
                self.validation_suite.failed_tests += 1
            elif result.status == 'skipped':
                self.validation_suite.skipped_tests += 1
            else:
                self.validation_suite.error_tests += 1
            
            # Check if critical test failed
            if test_config.get('critical', False) and result.status in ['failed', 'error']:
                self.logger.warning(f"Critical test {result.test_name} failed - considering repair mode")
                if self.repair_mode:
                    await self._attempt_repair(test_config, result)
        
        # Calculate final metrics
        suite_end = datetime.now()
        self.validation_suite.end_time = suite_end.isoformat()
        self.validation_suite.duration = (suite_end - suite_start).total_seconds()
        
        # Determine overall status
        if self.validation_suite.error_tests > 0:
            self.validation_suite.overall_status = 'error'
        elif self.validation_suite.failed_tests > 0:
            self.validation_suite.overall_status = 'failed'
        elif self.validation_suite.passed_tests == self.validation_suite.total_tests:
            self.validation_suite.overall_status = 'passed'
        else:
            self.validation_suite.overall_status = 'partial'
        
        self.logger.info(f"Validation suite completed: {self.validation_suite.overall_status}")
        return self.validation_suite
    
    async def _attempt_repair(self, test_config: Dict[str, Any], result: ValidationResult):
        """Attempt to repair failed critical test"""
        if not self.repair_mode:
            return
            
        self.logger.info(f"Attempting repair for failed test: {test_config['name']}")
        
        try:
            # Import automated repair system
            from automated_repair_recovery import AutomatedRepairSystem
            repair_system = AutomatedRepairSystem()
            
            # Attempt repair based on test type
            repair_actions = []
            if 'health' in test_config['name'].lower():
                repair_actions = ['restart_postgresql', 'check_postgresql_config']
            elif 'network' in test_config['name'].lower():
                repair_actions = ['restart_containers', 'check_network_config']
            elif 'connection' in test_config['name'].lower():
                repair_actions = ['reset_connection_pool', 'update_database_config']
            elif 'table' in test_config['name'].lower():
                repair_actions = ['reinitialize_database', 'rebuild_schema']
            
            if repair_actions:
                for action in repair_actions:
                    try:
                        self.logger.info(f"Executing repair action: {action}")
                        # This would call the actual repair methods
                        # For now, just log the attempt
                        await asyncio.sleep(1)  # Simulate repair time
                    except Exception as repair_error:
                        self.logger.error(f"Repair action {action} failed: {repair_error}")
                        
        except Exception as e:
            self.logger.error(f"Repair attempt failed: {e}")
    
    def generate_report(self) -> str:
        """Generate a comprehensive validation report"""
        report = []
        report.append("=" * 80)
        report.append("DATABASE CONNECTIVITY VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Suite: {self.validation_suite.suite_name}")
        report.append(f"Start Time: {self.validation_suite.start_time}")
        report.append(f"End Time: {self.validation_suite.end_time}")
        report.append(f"Duration: {self.validation_suite.duration:.2f} seconds")
        report.append(f"Overall Status: {self.validation_suite.overall_status.upper()}")
        report.append("")
        
        # Summary
        report.append("SUMMARY:")
        report.append(f"  Total Tests: {self.validation_suite.total_tests}")
        report.append(f"  Passed: {self.validation_suite.passed_tests}")
        report.append(f"  Failed: {self.validation_suite.failed_tests}")
        report.append(f"  Errors: {self.validation_suite.error_tests}")
        report.append(f"  Skipped: {self.validation_suite.skipped_tests}")
        report.append("")
        
        # Individual test results
        report.append("DETAILED RESULTS:")
        report.append("-" * 80)
        
        for result in self.validation_suite.results:
            status_symbol = {
                'passed': '✓',
                'failed': '✗',
                'error': '!',
                'skipped': '-'
            }.get(result.status, '?')
            
            report.append(f"{status_symbol} {result.test_name}")
            report.append(f"    Status: {result.status.upper()}")
            report.append(f"    Duration: {result.duration:.2f}s")
            report.append(f"    Message: {result.message}")
            if result.details and self.verbose:
                report.append(f"    Details: {json.dumps(result.details, indent=6)}")
            report.append("")
        
        return "\n".join(report)
    
    def save_report(self, filename: Optional[str] = None) -> str:
        """Save validation report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tests/master_validation_report_{timestamp}.txt"
        
        report_content = self.generate_report()
        
        with open(filename, 'w') as f:
            f.write(report_content)
        
        # Also save JSON data for programmatic access
        json_filename = filename.replace('.txt', '.json')
        with open(json_filename, 'w') as f:
            json.dump(asdict(self.validation_suite), f, indent=2)
        
        return filename

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Master Database Validation Runner')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--repair', '-r', action='store_true', help='Enable repair mode for critical failures')
    parser.add_argument('--output', '-o', type=str, help='Output report filename')
    parser.add_argument('--json-only', action='store_true', help='Output only JSON results')
    
    args = parser.parse_args()
    
    # Create and run validation suite
    runner = MasterValidationRunner(verbose=args.verbose, repair_mode=args.repair)
    
    try:
        validation_suite = await runner.run_validation_suite()
        
        if not args.json_only:
            print(runner.generate_report())
        
        # Save report
        report_file = runner.save_report(args.output)
        print(f"\nReport saved to: {report_file}")
        
        if args.json_only:
            json_file = report_file.replace('.txt', '.json')
            with open(json_file, 'r') as f:
                print(json.load(f))
        
        # Exit with appropriate code
        exit_code = 0 if validation_suite.overall_status == 'passed' else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"Validation suite failed: {e}")
        sys.exit(3)

if __name__ == "__main__":
    asyncio.run(main())