#!/usr/bin/env python3
"""
Frame-Based Validation Test Runner

This script runs the comprehensive frame-based validation test suite and provides
detailed reporting on test results, addressing the user's concern about frame 
correlation in detection measurements.

Usage:
    python3 run_frame_validation_tests.py
    python3 run_frame_validation_tests.py --comprehensive  # Run all tests
    python3 run_frame_validation_tests.py --known-session  # Run known session test only
    python3 run_frame_validation_tests.py --edge-cases     # Run edge cases only
    python3 run_frame_validation_tests.py --camera-latency # Run camera validation only
"""

import subprocess
import sys
import os
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

def run_test_suite(test_file: str, test_class: str = None, test_method: str = None, verbose: bool = True):
    """Run a specific test suite and return results"""
    
    # Build pytest command
    cmd = ["python3", "-m", "pytest"]
    
    # Build test path
    test_path = f"tests/{test_file}"
    if test_class:
        test_path += f"::{test_class}"
    if test_method:
        test_path += f"::{test_method}"
    
    cmd.append(test_path)
    
    # Add options
    if verbose:
        cmd.extend(["-v", "--tb=short"])
    
    cmd.extend(["-x", "--no-header"])  # Stop on first failure, no header
    
    print(f"🧪 Running: {' '.join(cmd)}")
    print("="*70)
    
    try:
        # Run test
        result = subprocess.run(cmd, cwd=backend_path, capture_output=True, text=True, timeout=300)
        
        return {
            "command": " ".join(cmd),
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(cmd),
            "return_code": -1,
            "stdout": "",
            "stderr": "Test timed out after 300 seconds",
            "success": False
        }
    
    except Exception as e:
        return {
            "command": " ".join(cmd),
            "return_code": -1,
            "stdout": "",
            "stderr": f"Test execution error: {str(e)}",
            "success": False
        }

def run_comprehensive_frame_validation():
    """Run the comprehensive frame-based validation test suite"""
    print("🎯 COMPREHENSIVE FRAME-BASED VALIDATION TEST SUITE")
    print("="*70)
    print("Testing detection events with frame correlation vs misaligned frames")
    print("Testing latency calculations with frame-specific timing")
    print("Testing UI display of frame correlation data")
    print("Testing edge cases with missing/inconsistent frame data")
    print("Using known session: 2802a2b7-8c8d-45a2-a2cf-d56261ff6cd7")
    print("Validating 215-235ms latencies for camera performance")
    print("")
    
    # Run comprehensive tests
    result = run_test_suite(
        "test_frame_based_validation_comprehensive.py",
        "TestFrameBasedValidationComprehensive"
    )
    
    print("\n" + "="*70)
    print("COMPREHENSIVE FRAME VALIDATION RESULTS")
    print("="*70)
    
    if result["success"]:
        print("✅ ALL COMPREHENSIVE TESTS PASSED!")
        print("✅ Frame correlation significantly improves detection accuracy")
        print("✅ Latency calculations properly account for frame-specific timing")
        print("✅ UI display of frame correlation data validated")
        print("✅ Edge cases with missing frame data handled gracefully")
        print("✅ Known session with 24 ground truth events validated")
        print("✅ Camera latency range 215-235ms properly measured")
    else:
        print("❌ COMPREHENSIVE TESTS FAILED")
        print(f"Return code: {result['return_code']}")
        if result["stderr"]:
            print(f"Error output:\n{result['stderr']}")
    
    if result["stdout"]:
        print(f"\nTest output:\n{result['stdout']}")
    
    return result

def run_known_session_test():
    """Run the specific known session test"""
    print("🎯 KNOWN SESSION VALIDATION TEST")
    print("="*70)
    print("Session ID: 2802a2b7-8c8d-45a2-a2cf-d56261ff6cd7")
    print("Ground Truth Events: 24")
    print("Expected Latency Range: 215-235ms")
    print("Testing frame correlation for camera validation")
    print("")
    
    result = run_test_suite(
        "test_frame_based_validation_comprehensive.py",
        "TestFrameBasedValidationComprehensive",
        "test_known_session_validation_with_24_ground_truth_events"
    )
    
    print("\n" + "="*70)
    print("KNOWN SESSION TEST RESULTS")
    print("="*70)
    
    if result["success"]:
        print("✅ KNOWN SESSION TEST PASSED!")
        print("✅ 24 ground truth events properly correlated")
        print("✅ 215-235ms latency range validated")
        print("✅ Frame correlation addresses user concern")
        print("✅ Detection measurements correlate to correct video frames")
    else:
        print("❌ KNOWN SESSION TEST FAILED")
        print("❌ Frame correlation may need improvement")
    
    return result

def run_edge_cases_test():
    """Run the edge cases test suite"""
    print("🎯 FRAME TIMING EDGE CASES TEST SUITE")
    print("="*70)
    print("Testing missing frame numbers in detection events")
    print("Testing inconsistent frame timing data")
    print("Testing frame data corruption scenarios")
    print("Testing frame synchronization drift over time")
    print("Testing frame rate mismatch scenarios")
    print("")
    
    result = run_test_suite(
        "test_frame_timing_synchronization_edge_cases.py",
        "TestFrameTimingSynchronizationEdgeCases"
    )
    
    print("\n" + "="*70)
    print("EDGE CASES TEST RESULTS")
    print("="*70)
    
    if result["success"]:
        print("✅ ALL EDGE CASES HANDLED SUCCESSFULLY!")
        print("✅ Missing frame data handled gracefully")
        print("✅ Inconsistent frame timing detected and corrected")
        print("✅ Frame data corruption scenarios managed")
        print("✅ Frame synchronization drift compensated")
        print("✅ Frame rate mismatches handled")
    else:
        print("❌ EDGE CASES TEST FAILED")
        print("❌ Review edge case handling implementation")
    
    return result

def run_camera_latency_test():
    """Run the camera latency validation test suite"""
    print("🎯 CAMERA LATENCY FRAME VALIDATION TEST SUITE")
    print("="*70)
    print("Testing camera latency measurement accuracy")
    print("Testing frame correlation improvement for camera validation")
    print("Testing camera performance assessment with frames")
    print("Addressing user concern about frame information")
    print("")
    
    result = run_test_suite(
        "test_camera_latency_frame_validation.py",
        "TestCameraLatencyFrameValidation"
    )
    
    print("\n" + "="*70)
    print("CAMERA LATENCY TEST RESULTS")
    print("="*70)
    
    if result["success"]:
        print("✅ ALL CAMERA LATENCY TESTS PASSED!")
        print("✅ Camera latency measurement accuracy validated")
        print("✅ Frame correlation significantly improves camera validation")
        print("✅ Camera performance assessment enabled by frame data")
        print("✅ User concern about frame information fully addressed")
    else:
        print("❌ CAMERA LATENCY TESTS FAILED")
        print("❌ Review camera validation frame correlation")
    
    return result

def generate_test_report(results: dict):
    """Generate comprehensive test report"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"frame_validation_test_report_{timestamp}.json"
    
    # Calculate overall statistics
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r["success"])
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    # Generate report
    report = {
        "test_run_timestamp": datetime.now().isoformat(),
        "test_suite": "Frame-Based Validation Comprehensive Test Suite",
        "summary": {
            "total_test_suites": total_tests,
            "passed_test_suites": passed_tests,
            "failed_test_suites": failed_tests,
            "success_rate_percentage": round(success_rate, 1),
            "overall_status": "PASSED" if passed_tests == total_tests else "FAILED"
        },
        "test_results": results,
        "conclusions": {
            "frame_correlation_validation": passed_tests >= 3,
            "user_concern_addressed": "test_known_session" in results and results["test_known_session"]["success"],
            "camera_validation_improved": "test_camera_latency" in results and results["test_camera_latency"]["success"],
            "edge_cases_handled": "test_edge_cases" in results and results["test_edge_cases"]["success"],
            "production_ready": passed_tests == total_tests
        },
        "recommendations": []
    }
    
    # Add recommendations based on results
    if not results.get("test_comprehensive", {}).get("success", False):
        report["recommendations"].append("Review comprehensive frame validation implementation")
    
    if not results.get("test_known_session", {}).get("success", False):
        report["recommendations"].append("Fix known session validation - critical for user concern")
    
    if not results.get("test_edge_cases", {}).get("success", False):
        report["recommendations"].append("Improve edge case handling for production robustness")
    
    if not results.get("test_camera_latency", {}).get("success", False):
        report["recommendations"].append("Address camera latency frame correlation issues")
    
    if not report["recommendations"]:
        report["recommendations"].append("All tests passed - frame-based validation ready for production")
    
    # Save report
    try:
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n📄 Detailed test report saved to: {report_file}")
    except Exception as e:
        print(f"\n⚠️  Could not save test report: {e}")
    
    return report

def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="Frame-Based Validation Test Runner")
    parser.add_argument("--comprehensive", action="store_true", 
                       help="Run comprehensive frame validation tests")
    parser.add_argument("--known-session", action="store_true",
                       help="Run known session validation test only")
    parser.add_argument("--edge-cases", action="store_true",
                       help="Run edge cases test suite only")
    parser.add_argument("--camera-latency", action="store_true",
                       help="Run camera latency validation test only")
    parser.add_argument("--all", action="store_true",
                       help="Run all test suites")
    
    args = parser.parse_args()
    
    # If no specific test specified, run all
    if not any([args.comprehensive, args.known_session, args.edge_cases, args.camera_latency]):
        args.all = True
    
    print("🚀 FRAME-BASED VALIDATION TEST RUNNER")
    print("="*70)
    print("Testing frame correlation improvements for detection validation")
    print("Addressing user concern: 'why is the frame not mentioned for detection'")
    print("Validating camera performance with frame-accurate measurements")
    print("="*70)
    print("")
    
    # Track results
    results = {}
    
    # Run selected tests
    if args.comprehensive or args.all:
        print("🧪 Running Comprehensive Frame Validation Tests...")
        results["test_comprehensive"] = run_comprehensive_frame_validation()
        print("")
    
    if args.known_session or args.all:
        print("🧪 Running Known Session Validation Test...")
        results["test_known_session"] = run_known_session_test()
        print("")
    
    if args.edge_cases or args.all:
        print("🧪 Running Edge Cases Test Suite...")
        results["test_edge_cases"] = run_edge_cases_test()
        print("")
    
    if args.camera_latency or args.all:
        print("🧪 Running Camera Latency Test Suite...")
        results["test_camera_latency"] = run_camera_latency_test()
        print("")
    
    # Generate final report
    print("📊 GENERATING COMPREHENSIVE TEST REPORT")
    print("="*70)
    
    report = generate_test_report(results)
    
    # Print final summary
    print("\n🎯 FINAL TEST SUMMARY")
    print("="*70)
    print(f"Test Suites Run: {report['summary']['total_test_suites']}")
    print(f"Passed: {report['summary']['passed_test_suites']} ✅")
    print(f"Failed: {report['summary']['failed_test_suites']} ❌")
    print(f"Success Rate: {report['summary']['success_rate_percentage']:.1f}%")
    print(f"Overall Status: {report['summary']['overall_status']}")
    
    print(f"\n🔍 VALIDATION CONCLUSIONS")
    print("="*70)
    conclusions = report["conclusions"]
    print(f"Frame correlation validation: {'✅ PASSED' if conclusions['frame_correlation_validation'] else '❌ FAILED'}")
    print(f"User concern addressed: {'✅ YES' if conclusions['user_concern_addressed'] else '❌ NO'}")
    print(f"Camera validation improved: {'✅ YES' if conclusions['camera_validation_improved'] else '❌ NO'}")
    print(f"Edge cases handled: {'✅ YES' if conclusions['edge_cases_handled'] else '❌ NO'}")
    print(f"Production ready: {'✅ YES' if conclusions['production_ready'] else '❌ NO'}")
    
    print(f"\n💡 RECOMMENDATIONS")
    print("="*70)
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"{i}. {rec}")
    
    # Exit with appropriate code
    if report['summary']['overall_status'] == "PASSED":
        print(f"\n🎉 ALL FRAME-BASED VALIDATION TESTS SUCCESSFUL!")
        print(f"✅ Frame correlation significantly improves detection accuracy")
        print(f"✅ User concern about frame information fully addressed")
        print(f"✅ Camera performance validation enabled by frame correlation")
        sys.exit(0)
    else:
        print(f"\n💥 SOME FRAME-BASED VALIDATION TESTS FAILED")
        print(f"❌ Review failed test suites and address issues")
        print(f"❌ Frame correlation implementation may need improvements")
        sys.exit(1)

if __name__ == "__main__":
    main()