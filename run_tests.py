#!/usr/bin/env python3
"""
LabJack T7 ADAS HIL Testing Platform - Test Runner
Comprehensive testing suite with hardware validation and performance metrics
"""

import os
import sys
import time
import json
import logging
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from labjack_t7_manager import LabJackT7Manager, LabJackConfig
from adas_hil_integration import AdasHilTester

def setup_logging(log_level=logging.INFO):
    """Setup logging configuration"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/home/rigade/Testing/docs/test_execution.log')
        ]
    )

def check_labjack_availability():
    """Check if LabJack T7 is available and not claimed"""
    logger = logging.getLogger(__name__)
    
    try:
        import ljm
        
        # Try to open connection briefly
        handle = ljm.openS("T7", "USB", "ANY")
        info = ljm.getHandleInfo(handle)
        ljm.close(handle)
        
        logger.info(f"LabJack T7 detected: Serial {info[2]}")
        return True, f"T7-{info[2]}"
        
    except ImportError:
        logger.warning("LJM library not available - using mock mode")
        return True, "MOCK"
        
    except Exception as e:
        if "CLAIMED_BY_ANOTHER_PROCESS" in str(e):
            logger.error(f"LabJack T7 is claimed by another process: {e}")
            return False, f"CLAIMED: {e}"
        else:
            logger.error(f"LabJack connection failed: {e}")
            return False, f"ERROR: {e}"

def run_basic_connectivity_test():
    """Run basic connectivity and functionality tests"""
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("BASIC CONNECTIVITY TEST")
    logger.info("="*60)
    
    test_results = {
        "test_name": "basic_connectivity",
        "timestamp": datetime.now().isoformat(),
        "results": {},
        "success": True,
        "errors": []
    }
    
    try:
        # Test 1: Initialize manager
        config = LabJackConfig()
        manager = LabJackT7Manager(config)
        
        # Test 2: Connection
        connection_start = time.perf_counter()
        connected = manager.connect()
        connection_time = (time.perf_counter() - connection_start) * 1000
        
        test_results["results"]["connection"] = {
            "success": connected,
            "time_ms": connection_time,
            "device_info": manager.device_info
        }
        
        if not connected:
            test_results["errors"].append("Failed to connect to LabJack")
            test_results["success"] = False
            return test_results
        
        logger.info(f"✅ Connected in {connection_time:.1f}ms")
        logger.info(f"   Device: {manager.device_info}")
        
        # Test 3: Analog reading
        read_start = time.perf_counter()
        analog_result = manager.read_analog_precise([0, 1, 2, 3])
        read_time = (time.perf_counter() - read_start) * 1000
        
        test_results["results"]["analog_read"] = {
            "success": True,
            "time_ms": read_time,
            "channels": analog_result["channels"],
            "sample_values": analog_result["values"][0]
        }
        
        logger.info(f"✅ Analog read in {read_time:.1f}ms")
        logger.info(f"   Values: {[f'{v:.3f}V' for v in analog_result['values'][0]]}")
        
        # Test 4: GPIO trigger
        trigger_start = time.perf_counter()
        trigger_success = manager.trigger_camera_capture(100)
        trigger_time = (time.perf_counter() - trigger_start) * 1000
        
        test_results["results"]["gpio_trigger"] = {
            "success": trigger_success,
            "time_ms": trigger_time,
            "pulse_width_us": 100
        }
        
        logger.info(f"✅ GPIO trigger in {trigger_time:.1f}ms")
        
        # Test 5: Performance metrics
        metrics = manager.get_performance_metrics()
        test_results["results"]["performance_metrics"] = {
            "connection_time": metrics["connection_time"],
            "read_latency_us": metrics["read_latency_us"],
            "write_latency_us": metrics["write_latency_us"],
            "error_count": metrics["error_count"]
        }
        
        # Test 6: Diagnostic
        diagnostic = manager.run_diagnostic()
        test_results["results"]["diagnostic"] = diagnostic
        
        if diagnostic["overall_status"] != "PASS":
            test_results["errors"].extend(diagnostic["issues"])
            logger.warning(f"⚠️  Diagnostic issues: {diagnostic['issues']}")
        else:
            logger.info("✅ All diagnostics passed")
        
        # Cleanup
        manager.disconnect()
        logger.info("✅ Basic connectivity test completed successfully")
        
    except Exception as e:
        test_results["success"] = False
        test_results["errors"].append(f"Test execution error: {str(e)}")
        logger.error(f"❌ Basic connectivity test failed: {e}")
    
    return test_results

def run_performance_validation():
    """Run performance and timing validation tests"""
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("PERFORMANCE VALIDATION TEST")
    logger.info("="*60)
    
    test_results = {
        "test_name": "performance_validation",
        "timestamp": datetime.now().isoformat(),
        "results": {},
        "success": True,
        "errors": []
    }
    
    try:
        manager = LabJackT7Manager()
        if not manager.connect():
            raise RuntimeError("Failed to connect for performance test")
        
        # Test 1: Timing precision
        logger.info("Testing timing precision...")
        latencies = []
        num_tests = 100
        
        for i in range(num_tests):
            start = time.perf_counter()
            manager.read_analog_precise([0])
            latency_us = (time.perf_counter() - start) * 1e6
            latencies.append(latency_us)
            
            if i % 20 == 0:
                logger.info(f"  Sample {i+1}/{num_tests}: {latency_us:.1f}µs")
        
        import numpy as np
        timing_stats = {
            "samples": num_tests,
            "mean_us": float(np.mean(latencies)),
            "std_us": float(np.std(latencies)),
            "min_us": float(np.min(latencies)),
            "max_us": float(np.max(latencies)),
            "jitter_us": float(np.std(latencies))
        }
        
        test_results["results"]["timing_precision"] = timing_stats
        
        logger.info(f"  Mean latency: {timing_stats['mean_us']:.1f}µs")
        logger.info(f"  Jitter (std): {timing_stats['std_us']:.1f}µs")
        logger.info(f"  Range: {timing_stats['min_us']:.1f} - {timing_stats['max_us']:.1f}µs")
        
        # Performance thresholds
        if timing_stats["mean_us"] > 2000:
            test_results["errors"].append(f"Average latency {timing_stats['mean_us']:.1f}µs exceeds 2000µs threshold")
        
        if timing_stats["jitter_us"] > 500:
            test_results["errors"].append(f"Timing jitter {timing_stats['jitter_us']:.1f}µs exceeds 500µs threshold")
        
        # Test 2: Sustained throughput
        logger.info("Testing sustained throughput...")
        duration_s = 5.0
        start_time = time.perf_counter()
        sample_count = 0
        
        while (time.perf_counter() - start_time) < duration_s:
            manager.read_analog_precise([0, 1])
            sample_count += 1
        
        actual_duration = time.perf_counter() - start_time
        throughput_hz = sample_count / actual_duration
        
        throughput_stats = {
            "duration_s": actual_duration,
            "samples": sample_count,
            "throughput_hz": throughput_hz
        }
        
        test_results["results"]["sustained_throughput"] = throughput_stats
        
        logger.info(f"  Duration: {actual_duration:.2f}s")
        logger.info(f"  Samples: {sample_count}")
        logger.info(f"  Throughput: {throughput_hz:.1f} Hz")
        
        # Test 3: GPIO timing
        logger.info("Testing GPIO trigger timing...")
        trigger_times = []
        
        for pulse_width in [50, 100, 200, 500]:
            times_for_width = []
            for _ in range(10):
                start = time.perf_counter()
                manager.trigger_camera_capture(pulse_width)
                trigger_time_us = (time.perf_counter() - start) * 1e6
                times_for_width.append(trigger_time_us)
            
            avg_time = np.mean(times_for_width)
            trigger_times.append({
                "pulse_width_us": pulse_width,
                "avg_time_us": float(avg_time),
                "samples": times_for_width
            })
            
            logger.info(f"  Pulse {pulse_width}µs: avg {avg_time:.1f}µs")
        
        test_results["results"]["gpio_timing"] = trigger_times
        
        manager.disconnect()
        
        if len(test_results["errors"]) == 0:
            logger.info("✅ Performance validation completed successfully")
        else:
            test_results["success"] = False
            logger.warning(f"⚠️  Performance issues detected: {len(test_results['errors'])} errors")
        
    except Exception as e:
        test_results["success"] = False
        test_results["errors"].append(f"Performance test error: {str(e)}")
        logger.error(f"❌ Performance validation failed: {e}")
    
    return test_results

async def run_adas_hil_integration():
    """Run complete ADAS HIL integration test"""
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("ADAS HIL INTEGRATION TEST")
    logger.info("="*60)
    
    test_results = {
        "test_name": "adas_hil_integration",
        "timestamp": datetime.now().isoformat(),
        "results": {},
        "success": True,
        "errors": []
    }
    
    try:
        # Initialize HIL tester
        hil_tester = AdasHilTester()
        
        # Initialize platform
        init_success = await hil_tester.initialize()
        test_results["results"]["initialization"] = {
            "success": init_success,
            "device_connected": hil_tester.labjack.connected,
            "scenarios_loaded": len(hil_tester.test_scenarios)
        }
        
        if not init_success:
            raise RuntimeError("Failed to initialize HIL testing platform")
        
        logger.info(f"✅ HIL platform initialized with {len(hil_tester.test_scenarios)} scenarios")
        
        # Run test scenarios
        scenario_results = {}
        
        for scenario_name in ["pedestrian_crossing", "cyclist_approach"]:
            logger.info(f"Running scenario: {scenario_name}")
            
            results = await hil_tester.execute_test_scenario(scenario_name, iterations=2)
            
            passed = sum(1 for r in results if r.success)
            scenario_summary = {
                "total": len(results),
                "passed": passed,
                "failed": len(results) - passed,
                "success_rate": passed / len(results),
                "avg_detection_latency_ms": sum(r.detection_latency_ms for r in results) / len(results),
                "avg_camera_latency_us": sum(r.camera_trigger_latency_us for r in results) / len(results)
            }
            
            scenario_results[scenario_name] = scenario_summary
            
            logger.info(f"  Results: {passed}/{len(results)} passed")
            logger.info(f"  Avg detection latency: {scenario_summary['avg_detection_latency_ms']:.1f}ms")
            logger.info(f"  Avg camera latency: {scenario_summary['avg_camera_latency_us']:.1f}µs")
        
        test_results["results"]["scenarios"] = scenario_results
        
        # Get performance statistics
        performance_stats = hil_tester.get_test_report()
        test_results["results"]["performance_stats"] = performance_stats["performance_stats"]
        test_results["results"]["hardware_metrics"] = performance_stats["hardware_metrics"]
        
        await hil_tester.cleanup()
        
        # Calculate overall success
        overall_passed = sum(s["passed"] for s in scenario_results.values())
        overall_total = sum(s["total"] for s in scenario_results.values())
        overall_success_rate = overall_passed / overall_total if overall_total > 0 else 0
        
        test_results["results"]["overall"] = {
            "total_tests": overall_total,
            "passed": overall_passed,
            "success_rate": overall_success_rate
        }
        
        if overall_success_rate < 1.0:
            test_results["errors"].append(f"Some scenario tests failed: {overall_passed}/{overall_total} passed")
            test_results["success"] = overall_success_rate > 0.5  # Pass if > 50% success
        
        logger.info(f"✅ ADAS HIL integration test completed: {overall_success_rate:.1%} success rate")
        
    except Exception as e:
        test_results["success"] = False
        test_results["errors"].append(f"HIL integration error: {str(e)}")
        logger.error(f"❌ ADAS HIL integration test failed: {e}")
    
    return test_results

def run_pytest_suite():
    """Run pytest test suite"""
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("PYTEST UNIT TEST SUITE")
    logger.info("="*60)
    
    try:
        # Run pytest with coverage
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/test_labjack_t7_manager.py",
            "-v",
            "--tb=short",
            "--no-header"
        ], capture_output=True, text=True, cwd="/home/rigade/Testing")
        
        success = result.returncode == 0
        
        logger.info("PyTest Output:")
        logger.info(result.stdout)
        
        if result.stderr:
            logger.warning("PyTest Errors:")
            logger.warning(result.stderr)
        
        if success:
            logger.info("✅ PyTest suite passed")
        else:
            logger.error("❌ PyTest suite failed")
        
        return {
            "success": success,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to run PyTest: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def generate_test_report(all_results):
    """Generate comprehensive test report"""
    logger = logging.getLogger(__name__)
    
    report = {
        "test_execution": {
            "timestamp": datetime.now().isoformat(),
            "platform": "LabJack T7 ADAS HIL Testing Platform",
            "environment": {
                "python_version": sys.version,
                "working_directory": os.getcwd()
            }
        },
        "test_results": all_results,
        "summary": {
            "total_test_suites": len(all_results),
            "passed_suites": sum(1 for r in all_results.values() if r.get("success", False)),
            "failed_suites": sum(1 for r in all_results.values() if not r.get("success", False)),
            "overall_success": all(r.get("success", False) for r in all_results.values())
        }
    }
    
    # Save detailed report
    report_file = Path("/home/rigade/Testing/docs/test_report.json")
    report_file.parent.mkdir(exist_ok=True)
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"📊 Test report saved to: {report_file}")

    # Also propagate/copy results to optional locations so UI can pick them up
    try:
        # 1) Environment-controlled exact file path override
        env_results_path = os.environ.get("HIL_RESULTS_JSON")
        if env_results_path:
            try:
                Path(env_results_path).parent.mkdir(parents=True, exist_ok=True)
                with open(env_results_path, 'w') as f:
                    json.dump(report, f, indent=2)
                logger.info(f"📤 Test report also written to HIL_RESULTS_JSON: {env_results_path}")
            except Exception as e:
                logger.warning(f"Failed to write HIL_RESULTS_JSON ({env_results_path}): {e}")

        # 2) Environment-controlled directory; write as test_report.json
        env_results_dir = os.environ.get("HIL_RESULTS_DIR")
        if env_results_dir:
            try:
                out_dir = Path(env_results_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / "test_report.json"
                with open(out_file, 'w') as f:
                    json.dump(report, f, indent=2)
                logger.info(f"📤 Test report also written to HIL_RESULTS_DIR: {out_file}")
            except Exception as e:
                logger.warning(f"Failed to write HIL_RESULTS_DIR ({env_results_dir}): {e}")

        # 3) If frontend memory folder exists, mirror there for the Results page
        frontend_memory = Path("/home/rigade/Testing/ai-model-validation-platform/frontend/memory")
        if frontend_memory.exists() and frontend_memory.is_dir():
            try:
                mirror_path = frontend_memory / "test_report.json"
                with open(mirror_path, 'w') as f:
                    json.dump(report, f, indent=2)
                logger.info(f"🪞 Test report mirrored to frontend memory: {mirror_path}")
            except Exception as e:
                logger.warning(f"Failed to mirror report to frontend memory: {e}")
    except Exception as e:
        logger.warning(f"Result propagation encountered an issue: {e}")
    
    # Print summary
    logger.info("="*80)
    logger.info("TEST EXECUTION SUMMARY")
    logger.info("="*80)
    
    summary = report["summary"]
    logger.info(f"Test Suites: {summary['passed_suites']}/{summary['total_test_suites']} passed")
    logger.info(f"Overall Status: {'✅ PASS' if summary['overall_success'] else '❌ FAIL'}")
    
    for test_name, result in all_results.items():
        status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
        error_count = len(result.get("errors", []))
        logger.info(f"  {test_name}: {status}" + (f" ({error_count} errors)" if error_count > 0 else ""))
    
    return report

async def main():
    """Main test execution"""
    parser = argparse.ArgumentParser(description="LabJack T7 ADAS HIL Testing Platform")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--quick", action="store_true", help="Run only basic tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    setup_logging(log_level)
    
    logger = logging.getLogger(__name__)
    logger.info("🚀 Starting LabJack T7 ADAS HIL Testing Platform")
    
    # Check LabJack availability
    available, status = check_labjack_availability()
    logger.info(f"LabJack Status: {status}")
    
    if not available:
        logger.error("LabJack T7 not available - some tests may fail")
    
    # Run test suites
    all_results = {}
    
    if args.quick or not (args.performance or args.integration):
        logger.info("Running basic connectivity test...")
        all_results["basic_connectivity"] = run_basic_connectivity_test()
        
        if args.quick:
            report = generate_test_report(all_results)
            return
    
    if args.performance or not (args.quick or args.integration):
        logger.info("Running performance validation...")
        all_results["performance_validation"] = run_performance_validation()
    
    if args.integration or not (args.quick or args.performance):
        logger.info("Running ADAS HIL integration test...")
        all_results["adas_hil_integration"] = await run_adas_hil_integration()
    
    # Always run unit tests
    logger.info("Running PyTest unit test suite...")
    all_results["pytest_suite"] = run_pytest_suite()
    
    # Generate final report
    report = generate_test_report(all_results)
    
    # Exit with appropriate code
    exit_code = 0 if report["summary"]["overall_success"] else 1
    logger.info(f"🏁 Test execution completed with exit code: {exit_code}")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())
