#!/usr/bin/env python3
"""
Quick Check Script for Database Validation System
Performs quick validation of all components and their integration.
"""

import sys
import os
import importlib
import traceback
from pathlib import Path

def check_module_import(module_name):
    """Check if a module can be imported"""
    try:
        module = importlib.import_module(module_name)
        return True, module, None
    except Exception as e:
        return False, None, str(e)

def check_class_instantiation(module_name, class_name):
    """Check if a class can be instantiated"""
    try:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        instance = cls()
        return True, instance, None
    except Exception as e:
        return False, None, str(e)

def main():
    """Main validation check"""
    print("=" * 80)
    print("DATABASE VALIDATION SYSTEM - QUICK CHECK")
    print("=" * 80)
    print()
    
    # Module and class mappings
    modules_to_check = {
        'db_health_check': 'PostgreSQLHealthChecker',
        'network_connectivity_test': 'NetworkConnectivityTester',
        'database_connection_validator': 'DatabaseConnectionValidator',
        'database_init_verifier': 'DatabaseInitializationVerifier',
        'table_creation_tester': 'TableCreationTester',
        'validate_all_tables': 'AllTablesValidator',
        'database_recovery_test': 'DatabaseRecoveryTester',
        'continuous_health_monitor': 'ContinuousHealthMonitor',
        'diagnostic_toolkit': 'DiagnosticToolkit',
        'automated_repair_recovery': 'AutomatedRepairSystem',
        'master_validation_runner': 'MasterValidationRunner'
    }
    
    results = {}
    total_checks = 0
    passed_checks = 0
    
    print("1. MODULE IMPORT CHECKS")
    print("-" * 40)
    
    for module_name, class_name in modules_to_check.items():
        total_checks += 1
        success, module, error = check_module_import(module_name)
        
        if success:
            print(f"✓ {module_name}: OK")
            passed_checks += 1
            results[module_name] = {'import': 'OK', 'class': None, 'error': None}
        else:
            print(f"✗ {module_name}: FAILED - {error}")
            results[module_name] = {'import': 'FAILED', 'class': None, 'error': error}
    
    print()
    print("2. CLASS INSTANTIATION CHECKS")  
    print("-" * 40)
    
    for module_name, class_name in modules_to_check.items():
        if results[module_name]['import'] == 'OK':
            total_checks += 1
            success, instance, error = check_class_instantiation(module_name, class_name)
            
            if success:
                print(f"✓ {class_name}: OK")
                passed_checks += 1
                results[module_name]['class'] = 'OK'
            else:
                print(f"✗ {class_name}: FAILED - {error}")
                results[module_name]['class'] = 'FAILED'
                results[module_name]['error'] = error
        else:
            print(f"- {class_name}: SKIPPED (import failed)")
            results[module_name]['class'] = 'SKIPPED'
    
    print()
    print("3. FILE EXISTENCE CHECKS")
    print("-" * 40)
    
    test_files = [f"{name}.py" for name in modules_to_check.keys()]
    
    for filename in test_files:
        total_checks += 1
        filepath = Path(__file__).parent / filename
        
        if filepath.exists():
            print(f"✓ {filename}: EXISTS")
            passed_checks += 1
        else:
            print(f"✗ {filename}: MISSING")
    
    print()
    print("4. MASTER RUNNER CONFIGURATION CHECK")
    print("-" * 40)
    
    try:
        from master_validation_runner import MasterValidationRunner
        runner = MasterValidationRunner()
        
        total_checks += 1
        if len(runner.test_sequence) > 0:
            print(f"✓ Test sequence configured: {len(runner.test_sequence)} tests")
            passed_checks += 1
        else:
            print("✗ No test sequence configured")
            
        total_checks += 1
        required_fields = ['name', 'module', 'class', 'method']
        all_valid = True
        for test_config in runner.test_sequence:
            for field in required_fields:
                if field not in test_config:
                    all_valid = False
                    break
            if not all_valid:
                break
                
        if all_valid:
            print("✓ All test configurations valid")
            passed_checks += 1
        else:
            print("✗ Invalid test configuration found")
            
    except Exception as e:
        total_checks += 2  # For the two checks above
        print(f"✗ Master runner check failed: {e}")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {total_checks - passed_checks}")
    print(f"Success rate: {(passed_checks / total_checks * 100):.1f}%")
    
    if passed_checks == total_checks:
        print("✓ ALL CHECKS PASSED - System ready for validation")
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Review errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())