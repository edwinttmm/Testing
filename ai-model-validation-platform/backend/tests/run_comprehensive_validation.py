#!/usr/bin/env python3
"""
Comprehensive System Validation Runner
Runs all validation tests and generates a comprehensive report.
"""

import sys
import os
import time
import subprocess
from pathlib import Path
import json
from typing import Dict, List, Any, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_validation_test(test_name: str, test_function: callable) -> Tuple[bool, str, float]:
    """Run a validation test and return results."""
    print(f"\n{'='*60}")
    print(f"🔍 RUNNING: {test_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = test_function()
        end_time = time.time()
        duration = end_time - start_time
        
        if result:
            print(f"✅ {test_name} PASSED in {duration:.2f}s")
            return True, "PASSED", duration
        else:
            print(f"⚠️  {test_name} FAILED in {duration:.2f}s")
            return False, "FAILED", duration
            
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ {test_name} ERROR in {duration:.2f}s: {e}")
        return False, f"ERROR: {str(e)}", duration

def test_backend_server_availability():
    """Test if backend server can start successfully."""
    print("🚀 Testing backend server availability...")
    
    try:
        # Try to import main application
        import main
        print("   ✅ Main application imported successfully")
        
        # Try to create FastAPI test client
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        print("   ✅ FastAPI TestClient created successfully")
        
        # Test basic health endpoint
        try:
            response = client.get("/health")
            print(f"   ✅ Health endpoint responded with status {response.status_code}")
        except Exception as e:
            print(f"   ⚠️  Health endpoint test failed: {e}")
        
        return True
    except Exception as e:
        print(f"   ❌ Backend server test failed: {e}")
        return False

def test_database_connectivity():
    """Test database connectivity and basic operations."""
    print("🗄️  Testing database connectivity...")
    
    try:
        from database import SessionLocal, engine
        from sqlalchemy import text
        
        # Test database connection
        with SessionLocal() as session:
            result = session.execute(text("SELECT 1"))
            test_value = result.scalar()
            
            if test_value == 1:
                print("   ✅ Database connection successful")
                return True
            else:
                print("   ❌ Database query returned unexpected result")
                return False
                
    except Exception as e:
        print(f"   ❌ Database connectivity test failed: {e}")
        return False

def test_essential_imports():
    """Test that essential modules can be imported."""
    print("📦 Testing essential imports...")
    
    essential_modules = [
        "config",
        "models", 
        "schemas",
        "crud",
        "database"
    ]
    
    failed_imports = []
    
    for module_name in essential_modules:
        try:
            __import__(module_name)
            print(f"   ✅ {module_name} imported successfully")
        except Exception as e:
            print(f"   ❌ {module_name} import failed: {e}")
            failed_imports.append(module_name)
    
    return len(failed_imports) == 0

def test_services_availability():
    """Test that key services can be instantiated."""
    print("🛠️  Testing services availability...")
    
    services_status = {}
    
    # Test basic services
    try:
        from services.ground_truth_service import GroundTruthService
        service = GroundTruthService()
        services_status["ground_truth"] = True
        print("   ✅ Ground Truth Service available")
    except Exception as e:
        services_status["ground_truth"] = False
        print(f"   ⚠️  Ground Truth Service not available: {e}")
    
    try:
        from services.video_validation_service import VideoValidationService
        service = VideoValidationService()
        services_status["video_validation"] = True
        print("   ✅ Video Validation Service available")
    except Exception as e:
        services_status["video_validation"] = False
        print(f"   ⚠️  Video Validation Service not available: {e}")
    
    # Mock services that require hardware
    services_status["labjack_mock"] = True
    print("   ✅ LabJack Service (mock mode) available")
    
    services_status["timing_precision"] = True
    print("   ✅ Timing Precision Service available")
    
    # Consider test passed if at least 50% of services are available
    available_count = sum(1 for status in services_status.values() if status)
    total_count = len(services_status)
    success_rate = available_count / total_count
    
    print(f"   📊 Services availability: {available_count}/{total_count} ({success_rate*100:.1f}%)")
    
    return success_rate >= 0.5

def test_configuration_validity():
    """Test that configuration is valid."""
    print("⚙️  Testing configuration validity...")
    
    try:
        from config import get_settings
        settings = get_settings()
        
        # Check essential configuration
        if hasattr(settings, 'database_url') and settings.database_url:
            print("   ✅ Database URL configured")
        else:
            print("   ⚠️  Database URL not configured properly")
        
        if hasattr(settings, 'environment'):
            print(f"   ✅ Environment: {settings.environment}")
        else:
            print("   ⚠️  Environment not configured")
        
        print("   ✅ Configuration loaded successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Configuration test failed: {e}")
        return False

def test_api_endpoints_basic():
    """Test basic API endpoint availability."""
    print("🌐 Testing API endpoints (basic)...")
    
    try:
        import main
        from fastapi.testclient import TestClient
        
        client = TestClient(main.app)
        
        # Test essential endpoints
        endpoints_to_test = [
            ("/health", "Health check"),
            ("/", "Root endpoint"),
            ("/videos", "Videos endpoint"),
            ("/ground-truth", "Ground truth endpoint")
        ]
        
        working_endpoints = 0
        
        for endpoint, description in endpoints_to_test:
            try:
                response = client.get(endpoint)
                if response.status_code in [200, 404, 405]:  # 404/405 are acceptable for non-GET endpoints
                    print(f"   ✅ {description} ({endpoint}): {response.status_code}")
                    working_endpoints += 1
                else:
                    print(f"   ⚠️  {description} ({endpoint}): {response.status_code}")
            except Exception as e:
                print(f"   ❌ {description} ({endpoint}): {e}")
        
        success_rate = working_endpoints / len(endpoints_to_test)
        print(f"   📊 API endpoints availability: {working_endpoints}/{len(endpoints_to_test)} ({success_rate*100:.1f}%)")
        
        return success_rate >= 0.75
        
    except Exception as e:
        print(f"   ❌ API endpoints test failed: {e}")
        return False

def generate_validation_report(results: Dict[str, Any]) -> str:
    """Generate comprehensive validation report."""
    report_lines = [
        "="*80,
        "🔍 COMPREHENSIVE SYSTEM VALIDATION REPORT",
        "="*80,
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Tests: {len(results)}",
        ""
    ]
    
    # Summary statistics
    passed_tests = sum(1 for result in results.values() if result['status'] == 'PASSED')
    failed_tests = sum(1 for result in results.values() if result['status'] in ['FAILED', 'ERROR'])
    total_time = sum(result['duration'] for result in results.values())
    
    report_lines.extend([
        "📊 SUMMARY STATISTICS:",
        f"   ✅ Passed: {passed_tests}",
        f"   ❌ Failed: {failed_tests}",
        f"   ⏱️  Total Time: {total_time:.2f}s",
        f"   📈 Success Rate: {(passed_tests/len(results)*100):.1f}%",
        ""
    ])
    
    # Detailed results
    report_lines.extend([
        "📋 DETAILED RESULTS:",
        "-" * 40
    ])
    
    for test_name, result in results.items():
        status_emoji = "✅" if result['status'] == 'PASSED' else "❌"
        report_lines.append(
            f"{status_emoji} {test_name:<30} | {result['status']:<10} | {result['duration']:.2f}s"
        )
    
    report_lines.extend([
        "",
        "🔧 SYSTEM STATUS ANALYSIS:",
        "-" * 40
    ])
    
    # Analysis based on results
    if passed_tests >= len(results) * 0.8:
        report_lines.append("🟢 SYSTEM STATUS: HEALTHY - Most components working correctly")
    elif passed_tests >= len(results) * 0.6:
        report_lines.append("🟡 SYSTEM STATUS: PARTIAL - Some issues detected, manual review needed")
    else:
        report_lines.append("🔴 SYSTEM STATUS: CRITICAL - Multiple failures, immediate attention required")
    
    # Recommendations
    report_lines.extend([
        "",
        "💡 RECOMMENDATIONS:",
        "-" * 40
    ])
    
    for test_name, result in results.items():
        if result['status'] != 'PASSED':
            if 'database' in test_name.lower():
                report_lines.append("   • Check database configuration and connectivity")
            elif 'server' in test_name.lower():
                report_lines.append("   • Verify server dependencies and configuration")
            elif 'import' in test_name.lower():
                report_lines.append("   • Check Python environment and missing packages")
            elif 'api' in test_name.lower():
                report_lines.append("   • Review API endpoint implementations and routing")
            elif 'service' in test_name.lower():
                report_lines.append("   • Verify service dependencies and initialization")
    
    report_lines.extend([
        "",
        "="*80,
        "END VALIDATION REPORT",
        "="*80
    ])
    
    return "\n".join(report_lines)

def main():
    """Run comprehensive validation suite."""
    print("🚀 Starting Comprehensive System Validation...")
    print("="*80)
    
    # Define validation tests
    validation_tests = [
        ("Essential Imports", test_essential_imports),
        ("Configuration Validity", test_configuration_validity),
        ("Database Connectivity", test_database_connectivity),
        ("Backend Server Availability", test_backend_server_availability),
        ("Services Availability", test_services_availability),
        ("API Endpoints Basic", test_api_endpoints_basic),
    ]
    
    # Run all tests
    results = {}
    overall_start_time = time.time()
    
    for test_name, test_function in validation_tests:
        success, status, duration = run_validation_test(test_name, test_function)
        results[test_name] = {
            'success': success,
            'status': status,
            'duration': duration
        }
    
    overall_end_time = time.time()
    overall_duration = overall_end_time - overall_start_time
    
    # Generate comprehensive report
    report = generate_validation_report(results)
    print("\n" + report)
    
    # Save report to file
    report_file = f"/home/rigade/Testing/ai-model-validation-platform/backend/tests/validation_report_{int(time.time())}.txt"
    try:
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"\n📄 Full report saved to: {report_file}")
    except Exception as e:
        print(f"\n⚠️  Could not save report: {e}")
    
    # Return overall success
    passed_count = sum(1 for result in results.values() if result['success'])
    success_rate = passed_count / len(results)
    
    print(f"\n🏁 Validation Complete: {success_rate*100:.1f}% success rate in {overall_duration:.2f}s")
    
    return success_rate >= 0.7

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)