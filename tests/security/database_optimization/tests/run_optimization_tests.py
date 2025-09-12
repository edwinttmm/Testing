#!/usr/bin/env python3
"""
Test runner for database cascade delete optimization validation.
Executes all tests to ensure the optimization works correctly and maintains data integrity.
"""

import sys
import os
import subprocess
import json
from datetime import datetime

def run_test_suite():
    """Run all cascade delete optimization tests"""
    test_dir = os.path.dirname(__file__)
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_results": {},
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }
    }
    
    test_files = [
        "test_cascade_deletes.py",
        "test_data_integrity.py", 
        "test_performance_comparison.py"
    ]
    
    print("=" * 80)
    print("DATABASE CASCADE DELETE OPTIMIZATION TEST SUITE")
    print("=" * 80)
    print()
    
    for test_file in test_files:
        test_path = os.path.join(test_dir, test_file)
        if not os.path.exists(test_path):
            print(f"❌ Test file not found: {test_file}")
            results["summary"]["errors"].append(f"Test file not found: {test_file}")
            continue
            
        print(f"🧪 Running {test_file}...")
        print("-" * 60)
        
        try:
            # Run pytest with verbose output and capture results
            cmd = [
                sys.executable, "-m", "pytest", 
                test_path, 
                "-v", 
                "--tb=short",
                "--no-header"
            ]
            
            process = subprocess.run(
                cmd, 
                cwd=test_dir,
                capture_output=True, 
                text=True,
                timeout=300  # 5 minute timeout per test file
            )
            
            # Parse test results
            output_lines = process.stdout.split('\n')
            test_count = 0
            passed_count = 0
            failed_count = 0
            
            for line in output_lines:
                if " PASSED " in line:
                    test_count += 1
                    passed_count += 1
                    print(f"  ✅ {line.split('::')[-1].split(' ')[0]}")
                elif " FAILED " in line:
                    test_count += 1
                    failed_count += 1
                    print(f"  ❌ {line.split('::')[-1].split(' ')[0]}")
                elif " ERROR " in line:
                    test_count += 1
                    failed_count += 1
                    print(f"  ⚠️  {line.split('::')[-1].split(' ')[0]}")
            
            # Store results
            results["test_results"][test_file] = {
                "total": test_count,
                "passed": passed_count,
                "failed": failed_count,
                "return_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr
            }
            
            results["summary"]["total_tests"] += test_count
            results["summary"]["passed"] += passed_count
            results["summary"]["failed"] += failed_count
            
            if process.returncode == 0:
                print(f"  ✅ {test_file}: {passed_count}/{test_count} tests passed")
            else:
                print(f"  ❌ {test_file}: {failed_count}/{test_count} tests failed")
                if process.stderr:
                    print(f"     Error: {process.stderr.strip()}")
                    results["summary"]["errors"].append(f"{test_file}: {process.stderr.strip()}")
                    
        except subprocess.TimeoutExpired:
            print(f"  ⏰ {test_file}: Test timed out after 5 minutes")
            results["summary"]["errors"].append(f"{test_file}: Test timed out")
            results["summary"]["failed"] += 1
            
        except Exception as e:
            print(f"  ⚠️  {test_file}: Error running test - {str(e)}")
            results["summary"]["errors"].append(f"{test_file}: {str(e)}")
            results["summary"]["failed"] += 1
        
        print()
    
    # Print summary
    print("=" * 80)
    print("TEST SUITE SUMMARY")
    print("=" * 80)
    
    total = results["summary"]["total_tests"]
    passed = results["summary"]["passed"] 
    failed = results["summary"]["failed"]
    
    print(f"📊 Total Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED - Database cascade delete optimization is working correctly!")
        success_rate = 100.0
    else:
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\n⚠️  {failed} tests failed - Success rate: {success_rate:.1f}%")
        
        if results["summary"]["errors"]:
            print("\nErrors encountered:")
            for error in results["summary"]["errors"]:
                print(f"  • {error}")
    
    print(f"\n📈 Success Rate: {success_rate:.1f}%")
    
    # Save detailed results
    results_file = os.path.join(test_dir, "test_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"📄 Detailed results saved to: {results_file}")
    
    # Return success/failure for CI/CD integration
    return failed == 0

def validate_optimization_implementation():
    """Validate that the cascade delete optimization was properly implemented"""
    print("\n🔍 VALIDATING OPTIMIZATION IMPLEMENTATION")
    print("-" * 80)
    
    # Check if models.py has proper cascade configurations
    backend_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'ai-model-validation-platform', 'backend')
    models_path = os.path.join(backend_path, 'models.py')
    crud_path = os.path.join(backend_path, 'crud.py')
    
    validation_results = {
        "models_cascade_config": False,
        "crud_optimization": False,
        "issues": []
    }
    
    # Check models.py for cascade configurations
    if os.path.exists(models_path):
        with open(models_path, 'r') as f:
            models_content = f.read()
            
        cascade_patterns = [
            'cascade="all, delete-orphan"',
            'videos = relationship("Video"',
            'test_sessions = relationship("TestSession"',
            'detection_events = relationship("DetectionEvent"'
        ]
        
        found_patterns = sum(1 for pattern in cascade_patterns if pattern in models_content)
        
        if found_patterns >= 3:
            print("✅ Models have proper cascade configurations")
            validation_results["models_cascade_config"] = True
        else:
            print(f"❌ Models missing cascade configurations (found {found_patterns}/4 patterns)")
            validation_results["issues"].append("Missing cascade configurations in models.py")
    else:
        print("❌ models.py not found")
        validation_results["issues"].append("models.py not found")
    
    # Check crud.py for optimization
    if os.path.exists(crud_path):
        with open(crud_path, 'r') as f:
            crud_content = f.read()
            
        # Check if manual deletion loops were removed
        manual_deletion_indicators = [
            "db.query(DetectionEvent).filter(",
            "db.query(TestSession).filter(",
            "synchronize_session=False"
        ]
        
        found_manual = sum(1 for indicator in manual_deletion_indicators if indicator in crud_content)
        
        if found_manual == 0:
            print("✅ CRUD operations optimized (manual deletion loops removed)")
            validation_results["crud_optimization"] = True
        else:
            print(f"❌ CRUD still contains manual deletion patterns ({found_manual} found)")
            validation_results["issues"].append("Manual deletion patterns still present in crud.py")
    else:
        print("❌ crud.py not found")
        validation_results["issues"].append("crud.py not found")
    
    # Overall validation
    if validation_results["models_cascade_config"] and validation_results["crud_optimization"]:
        print("\n🎉 OPTIMIZATION IMPLEMENTATION VALIDATED SUCCESSFULLY!")
        return True
    else:
        print(f"\n⚠️  OPTIMIZATION IMPLEMENTATION HAS ISSUES:")
        for issue in validation_results["issues"]:
            print(f"  • {issue}")
        return False

if __name__ == "__main__":
    print("Starting Database Cascade Delete Optimization Test Suite...")
    print(f"Test directory: {os.path.dirname(__file__)}")
    print()
    
    # Validate implementation first
    implementation_ok = validate_optimization_implementation()
    
    if implementation_ok:
        # Run tests
        tests_passed = run_test_suite()
        
        if tests_passed:
            print("\n🎉 DATABASE OPTIMIZATION COMPLETE AND VALIDATED!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed. Check the results above.")
            sys.exit(1)
    else:
        print("\n❌ Implementation validation failed. Fix issues before running tests.")
        sys.exit(1)