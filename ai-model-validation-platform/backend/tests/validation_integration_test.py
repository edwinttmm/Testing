#!/usr/bin/env python3
"""
Integration Test for Database Validation System
Tests the integration between all validation components.
"""

import asyncio
import sys
import os
import logging
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime
import json

# Add the backend directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class ValidationIntegrationTest(unittest.TestCase):
    """Integration tests for the validation system"""
    
    def setUp(self):
        """Setup for each test"""
        self.logger = logging.getLogger('integration_test')
        self.logger.setLevel(logging.INFO)
        
    def test_master_runner_imports(self):
        """Test that master runner can import all required modules"""
        try:
            from master_validation_runner import MasterValidationRunner
            self.assertIsNotNone(MasterValidationRunner)
            
            # Create runner instance
            runner = MasterValidationRunner(verbose=True)
            self.assertIsNotNone(runner)
            
            # Verify test sequence is properly defined
            self.assertGreater(len(runner.test_sequence), 0)
            
            # Verify all required fields are present in test configs
            required_fields = ['name', 'module', 'class', 'method', 'description']
            for test_config in runner.test_sequence:
                for field in required_fields:
                    self.assertIn(field, test_config, f"Missing field {field} in test config")
                    
        except ImportError as e:
            self.fail(f"Failed to import MasterValidationRunner: {e}")
    
    def test_validation_modules_available(self):
        """Test that all validation modules are available for import"""
        validation_modules = [
            'db_health_check',
            'network_connectivity_test', 
            'database_connection_validator',
            'database_init_verifier',
            'table_creation_tester',
            'validate_all_tables',
            'database_recovery_test',
            'continuous_health_monitor',
            'diagnostic_toolkit',
            'automated_repair_recovery'
        ]
        
        for module_name in validation_modules:
            try:
                module = __import__(module_name)
                self.assertIsNotNone(module, f"Module {module_name} imported as None")
            except ImportError as e:
                self.fail(f"Failed to import {module_name}: {e}")
    
    def test_validation_classes_available(self):
        """Test that all validation classes can be instantiated"""
        class_mappings = {
            'db_health_check': 'PostgreSQLHealthChecker',
            'network_connectivity_test': 'NetworkConnectivityTester',
            'database_connection_validator': 'DatabaseConnectionValidator',
            'database_init_verifier': 'DatabaseInitializationVerifier',
            'table_creation_tester': 'TableCreationTester',
            'validate_all_tables': 'AllTablesValidator',
            'database_recovery_test': 'DatabaseRecoveryTester',
            'continuous_health_monitor': 'ContinuousHealthMonitor',
            'diagnostic_toolkit': 'DiagnosticToolkit',
            'automated_repair_recovery': 'AutomatedRepairSystem'
        }
        
        for module_name, class_name in class_mappings.items():
            try:
                module = __import__(module_name, fromlist=[class_name])
                test_class = getattr(module, class_name)
                
                # Try to instantiate the class
                instance = test_class()
                self.assertIsNotNone(instance, f"Failed to instantiate {class_name}")
                
            except ImportError as e:
                self.fail(f"Failed to import {module_name}: {e}")
            except AttributeError as e:
                self.fail(f"Class {class_name} not found in {module_name}: {e}")
            except Exception as e:
                self.fail(f"Failed to instantiate {class_name}: {e}")
    
    @patch('master_validation_runner.MasterValidationRunner.run_single_test')
    async def test_master_runner_execution_flow(self, mock_run_test):
        """Test that master runner executes tests in correct sequence"""
        from master_validation_runner import MasterValidationRunner, ValidationResult
        
        # Mock successful test results
        mock_result = ValidationResult(
            test_name="Mock Test",
            status="passed", 
            duration=1.0,
            message="Mock test passed"
        )
        mock_run_test.return_value = mock_result
        
        runner = MasterValidationRunner(verbose=True)
        validation_suite = await runner.run_validation_suite()
        
        # Verify suite completed
        self.assertIsNotNone(validation_suite)
        self.assertEqual(validation_suite.overall_status, 'passed')
        self.assertEqual(len(validation_suite.results), len(runner.test_sequence))
        
        # Verify run_single_test was called for each test
        self.assertEqual(mock_run_test.call_count, len(runner.test_sequence))
    
    def test_validation_result_dataclass(self):
        """Test ValidationResult dataclass functionality"""
        from master_validation_runner import ValidationResult
        
        result = ValidationResult(
            test_name="Test Name",
            status="passed",
            duration=1.5,
            message="Test message"
        )
        
        self.assertEqual(result.test_name, "Test Name")
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.duration, 1.5)
        self.assertEqual(result.message, "Test message")
        self.assertIsNotNone(result.timestamp)
        self.assertIsNotNone(result.details)
    
    def test_validation_suite_dataclass(self):
        """Test ValidationSuite dataclass functionality"""
        from master_validation_runner import ValidationSuite, ValidationResult
        
        suite = ValidationSuite()
        
        # Verify default values
        self.assertEqual(suite.suite_name, "Database Connectivity Validation")
        self.assertIsNotNone(suite.start_time)
        self.assertEqual(suite.total_tests, 0)
        self.assertEqual(len(suite.results), 0)
        
        # Add a test result
        result = ValidationResult("Test", "passed", 1.0, "Success")
        suite.results.append(result)
        suite.total_tests = 1
        suite.passed_tests = 1
        
        self.assertEqual(len(suite.results), 1)
        self.assertEqual(suite.total_tests, 1)
    
    def test_report_generation(self):
        """Test report generation functionality"""
        from master_validation_runner import MasterValidationRunner, ValidationResult
        
        runner = MasterValidationRunner(verbose=True)
        
        # Add some mock results
        results = [
            ValidationResult("Test 1", "passed", 1.0, "Success"),
            ValidationResult("Test 2", "failed", 2.0, "Failure"),
            ValidationResult("Test 3", "error", 0.5, "Error occurred")
        ]
        
        runner.validation_suite.results = results
        runner.validation_suite.total_tests = 3
        runner.validation_suite.passed_tests = 1
        runner.validation_suite.failed_tests = 1
        runner.validation_suite.error_tests = 1
        runner.validation_suite.overall_status = "failed"
        
        report = runner.generate_report()
        
        # Verify report contains expected content
        self.assertIn("DATABASE CONNECTIVITY VALIDATION REPORT", report)
        self.assertIn("Total Tests: 3", report)
        self.assertIn("Passed: 1", report)
        self.assertIn("Failed: 1", report)
        self.assertIn("Errors: 1", report)
        self.assertIn("Test 1", report)
        self.assertIn("Test 2", report)
        self.assertIn("Test 3", report)
    
    def test_file_operations(self):
        """Test file operations and permissions"""
        test_files = [
            'db_health_check.py',
            'network_connectivity_test.py',
            'database_connection_validator.py',
            'database_init_verifier.py',
            'table_creation_tester.py',
            'validate_all_tables.py',
            'database_recovery_test.py',
            'continuous_health_monitor.py',
            'diagnostic_toolkit.py',
            'automated_repair_recovery.py',
            'master_validation_runner.py'
        ]
        
        for filename in test_files:
            filepath = Path(__file__).parent / filename
            
            # Verify file exists
            self.assertTrue(filepath.exists(), f"File {filename} does not exist")
            
            # Verify file is readable
            self.assertTrue(os.access(filepath, os.R_OK), f"File {filename} is not readable")
            
            # Verify file has content
            self.assertGreater(filepath.stat().st_size, 0, f"File {filename} is empty")
    
    @patch('builtins.open', create=True)
    def test_report_saving(self, mock_open):
        """Test report saving functionality"""
        from master_validation_runner import MasterValidationRunner
        
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        runner = MasterValidationRunner()
        
        # Test save report
        filename = runner.save_report("test_report.txt")
        
        # Verify file operations were called
        self.assertTrue(mock_open.called)
        self.assertTrue(mock_file.write.called)
        
        # Verify both text and JSON files are created
        self.assertEqual(mock_open.call_count, 2)  # One for .txt, one for .json
    
    def test_critical_vs_non_critical_tests(self):
        """Test handling of critical vs non-critical tests"""
        from master_validation_runner import MasterValidationRunner
        
        runner = MasterValidationRunner()
        
        # Verify critical tests are identified
        critical_tests = [test for test in runner.test_sequence if test.get('critical', False)]
        non_critical_tests = [test for test in runner.test_sequence if not test.get('critical', False)]
        
        self.assertGreater(len(critical_tests), 0, "No critical tests defined")
        self.assertGreater(len(non_critical_tests), 0, "No non-critical tests defined")
        
        # Verify critical tests include core functionality
        critical_names = [test['name'] for test in critical_tests]
        expected_critical = ['PostgreSQL Health Check', 'Database Connection Validation']
        
        for expected in expected_critical:
            self.assertTrue(
                any(expected in name for name in critical_names),
                f"Expected critical test containing '{expected}' not found"
            )

class AsyncValidationTest(unittest.TestCase):
    """Async-specific integration tests"""
    
    def test_async_test_execution(self):
        """Test async test execution capabilities"""
        async def sample_async_test():
            await asyncio.sleep(0.1)
            return {"success": True, "message": "Async test passed"}
        
        # Test that we can run async functions
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(sample_async_test())
            self.assertTrue(result["success"])
        finally:
            loop.close()
    
    def test_master_runner_async_compatibility(self):
        """Test that master runner works with async/await"""
        from master_validation_runner import MasterValidationRunner
        
        runner = MasterValidationRunner()
        
        # Verify that the main method is async
        self.assertTrue(asyncio.iscoroutinefunction(runner.run_validation_suite))
        self.assertTrue(asyncio.iscoroutinefunction(runner.run_single_test))

def run_integration_tests():
    """Run all integration tests"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(ValidationIntegrationTest))
    suite.addTests(loader.loadTestsFromTestCase(AsyncValidationTest))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Generate summary
    print("\n" + "="*80)
    print("INTEGRATION TEST SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    return len(result.failures) + len(result.errors) == 0

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)