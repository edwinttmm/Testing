"""
ADAS HIL Testing Platform Integration
Integrates LabJack T7 with camera system for Hardware-in-the-Loop testing
"""

import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import numpy as np
from concurrent.futures import ThreadPoolExecutor, Future
import threading

from labjack_t7_manager import LabJackT7Manager, LabJackConfig, TimingEvent

@dataclass
class TestScenario:
    """ADAS test scenario definition"""
    name: str
    description: str
    vru_type: str  # "pedestrian", "cyclist", "vehicle"
    detection_threshold: float
    timing_requirements: Dict[str, float]
    expected_signals: Dict[str, Tuple[float, float]]  # {channel: (min, max)}
    
@dataclass
class TestResult:
    """Test execution result"""
    scenario: TestScenario
    timestamp: datetime
    duration_ms: float
    detection_latency_ms: float
    camera_trigger_latency_us: float
    signal_quality: Dict[str, float]
    timing_precision_us: float
    success: bool
    errors: List[str]
    raw_data: Dict[str, Any]

class AdasHilTester:
    """ADAS HIL Testing Platform with LabJack T7 Integration"""
    
    def __init__(self, config: LabJackConfig = None):
        self.labjack = LabJackT7Manager(config)
        self.test_scenarios = {}
        self.test_results = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Performance monitoring
        self.performance_stats = {
            "tests_executed": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "avg_detection_latency_ms": 0.0,
            "avg_camera_latency_us": 0.0,
            "timing_accuracy_us": 0.0
        }
        
        # Load default test scenarios
        self._load_default_scenarios()
    
    def _load_default_scenarios(self):
        """Load default ADAS test scenarios"""
        scenarios = [
            TestScenario(
                name="pedestrian_crossing",
                description="Pedestrian crossing detection at 30 km/h",
                vru_type="pedestrian",
                detection_threshold=0.8,
                timing_requirements={
                    "max_detection_latency_ms": 100,
                    "max_camera_trigger_us": 500,
                    "timing_precision_us": 50
                },
                expected_signals={
                    "AIN0": (0.0, 5.0),  # Speed sensor
                    "AIN1": (0.0, 3.3),  # Distance sensor
                    "AIN2": (0.0, 3.3),  # Camera ready
                    "AIN3": (0.0, 5.0)   # VRU detection
                }
            ),
            TestScenario(
                name="cyclist_approach",
                description="Cyclist approach detection at 50 km/h",
                vru_type="cyclist",
                detection_threshold=0.7,
                timing_requirements={
                    "max_detection_latency_ms": 80,
                    "max_camera_trigger_us": 300,
                    "timing_precision_us": 30
                },
                expected_signals={
                    "AIN0": (1.0, 5.0),  # Higher speed
                    "AIN1": (0.5, 3.0),  # Variable distance
                    "AIN2": (0.0, 3.3),  # Camera ready
                    "AIN3": (0.0, 5.0)   # VRU detection
                }
            ),
            TestScenario(
                name="vehicle_cut_in",
                description="Vehicle cut-in scenario at highway speed",
                vru_type="vehicle",
                detection_threshold=0.9,
                timing_requirements={
                    "max_detection_latency_ms": 50,
                    "max_camera_trigger_us": 200,
                    "timing_precision_us": 20
                },
                expected_signals={
                    "AIN0": (3.0, 5.0),  # High speed
                    "AIN1": (2.0, 4.0),  # Close distance
                    "AIN2": (0.0, 3.3),  # Camera ready
                    "AIN3": (2.0, 5.0)   # Strong detection
                }
            )
        ]
        
        for scenario in scenarios:
            self.test_scenarios[scenario.name] = scenario
    
    async def initialize(self) -> bool:
        """Initialize the HIL testing platform"""
        try:
            # Connect to LabJack
            if not self.labjack.connect():
                raise RuntimeError("Failed to connect to LabJack T7")
            
            # Run initial diagnostic
            diagnostic = self.labjack.run_diagnostic()
            if diagnostic["overall_status"] != "PASS":
                self.logger.warning(f"Diagnostic issues detected: {diagnostic['issues']}")
            
            # Verify camera trigger functionality
            await self._verify_camera_system()
            
            # Initialize signal monitoring
            await self._initialize_signal_monitoring()
            
            self.logger.info("ADAS HIL Testing Platform initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False
    
    async def _verify_camera_system(self):
        """Verify camera trigger system"""
        self.logger.info("Verifying camera trigger system...")
        
        # Test trigger pulse timing
        for pulse_width in [50, 100, 200]:  # microseconds
            start_time = time.perf_counter()
            success = self.labjack.trigger_camera_capture(pulse_width)
            end_time = time.perf_counter()
            
            actual_duration = (end_time - start_time) * 1e6
            
            if not success:
                raise RuntimeError(f"Camera trigger failed at {pulse_width}µs")
            
            if actual_duration > pulse_width * 3:  # Allow 3x overhead
                self.logger.warning(f"Camera trigger slow: {actual_duration:.1f}µs for {pulse_width}µs pulse")
        
        self.logger.info("Camera trigger system verified")
    
    async def _initialize_signal_monitoring(self):
        """Initialize analog signal monitoring"""
        self.logger.info("Initializing signal monitoring...")
        
        # Read baseline signals
        baseline = self.labjack.read_analog_precise([0, 1, 2, 3], num_samples=10)
        
        # Calculate baseline statistics
        baseline_stats = {}
        for i, channel in enumerate(baseline["channels"]):
            channel_values = [sample[i] for sample in baseline["values"]]
            baseline_stats[f"AIN{channel}"] = {
                "mean": np.mean(channel_values),
                "std": np.std(channel_values),
                "min": np.min(channel_values),
                "max": np.max(channel_values)
            }
        
        self.baseline_signals = baseline_stats
        self.logger.info(f"Signal baselines established: {baseline_stats}")
    
    async def execute_test_scenario(self, scenario_name: str, 
                                  iterations: int = 1) -> List[TestResult]:
        """Execute a specific test scenario"""
        if scenario_name not in self.test_scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        scenario = self.test_scenarios[scenario_name]
        results = []
        
        self.logger.info(f"Executing scenario '{scenario_name}' with {iterations} iterations")
        
        for iteration in range(iterations):
            self.logger.debug(f"Iteration {iteration + 1}/{iterations}")
            
            # Execute single test
            result = await self._execute_single_test(scenario, iteration)
            results.append(result)
            
            # Update performance stats
            self._update_performance_stats(result)
            
            # Brief pause between iterations
            if iteration < iterations - 1:
                await asyncio.sleep(0.1)
        
        self.test_results.extend(results)
        
        # Log summary
        passed = sum(1 for r in results if r.success)
        self.logger.info(f"Scenario '{scenario_name}' completed: {passed}/{iterations} passed")
        
        return results
    
    async def _execute_single_test(self, scenario: TestScenario, 
                                 iteration: int) -> TestResult:
        """Execute a single test iteration"""
        test_start = time.perf_counter()
        errors = []
        raw_data = {
            "iteration": iteration,
            "baseline_readings": [],
            "trigger_events": [],
            "detection_events": [],
            "signal_measurements": []
        }
        
        try:
            # Step 1: Read baseline signals
            baseline = self.labjack.read_analog_precise([0, 1, 2, 3])
            raw_data["baseline_readings"] = baseline
            
            # Step 2: Trigger camera capture
            camera_trigger_start = time.perf_counter()
            trigger_success = self.labjack.trigger_camera_capture(100)
            camera_trigger_time = (time.perf_counter() - camera_trigger_start) * 1e6
            
            raw_data["trigger_events"].append({
                "success": trigger_success,
                "latency_us": camera_trigger_time,
                "timestamp": datetime.now().isoformat()
            })
            
            if not trigger_success:
                errors.append("Camera trigger failed")
            
            # Step 3: Monitor for VRU detection
            detection_start = time.perf_counter()
            vru_detection = self.labjack.wait_for_vru_detection(
                timeout_ms=int(scenario.timing_requirements["max_detection_latency_ms"] * 2)
            )
            detection_latency = (time.perf_counter() - detection_start) * 1000
            
            raw_data["detection_events"].append(vru_detection)
            
            # Step 4: Continuous signal monitoring during test
            monitoring_task = asyncio.create_task(
                self._monitor_signals_during_test(scenario, raw_data)
            )
            
            # Wait for monitoring to complete
            await monitoring_task
            
            # Step 5: Analyze results
            success, analysis_errors = self._analyze_test_results(
                scenario, raw_data, detection_latency, camera_trigger_time
            )
            
            errors.extend(analysis_errors)
            
            # Calculate signal quality metrics
            signal_quality = self._calculate_signal_quality(scenario, raw_data)
            
            # Calculate timing precision
            timing_events = [e for e in self.labjack.timing_events 
                           if e.timestamp >= datetime.fromtimestamp(test_start)]
            timing_precision = self._calculate_timing_precision(timing_events)
            
        except Exception as e:
            errors.append(f"Test execution error: {str(e)}")
            success = False
            detection_latency = 0.0
            camera_trigger_time = 0.0
            signal_quality = {}
            timing_precision = 0.0
        
        test_duration = (time.perf_counter() - test_start) * 1000
        
        result = TestResult(
            scenario=scenario,
            timestamp=datetime.now(),
            duration_ms=test_duration,
            detection_latency_ms=detection_latency,
            camera_trigger_latency_us=camera_trigger_time,
            signal_quality=signal_quality,
            timing_precision_us=timing_precision,
            success=success and len(errors) == 0,
            errors=errors,
            raw_data=raw_data
        )
        
        return result
    
    async def _monitor_signals_during_test(self, scenario: TestScenario, 
                                         raw_data: Dict[str, Any]):
        """Monitor analog signals during test execution"""
        monitoring_duration = 2.0  # seconds
        sample_interval = 0.01     # 10ms
        
        start_time = time.perf_counter()
        
        while (time.perf_counter() - start_time) < monitoring_duration:
            try:
                reading = self.labjack.read_analog_precise([0, 1, 2, 3])
                raw_data["signal_measurements"].append({
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_ms": (time.perf_counter() - start_time) * 1000,
                    "values": reading["values"][0],
                    "channels": reading["channels"]
                })
                
                await asyncio.sleep(sample_interval)
                
            except Exception as e:
                self.logger.warning(f"Signal monitoring error: {e}")
                break
    
    def _analyze_test_results(self, scenario: TestScenario, raw_data: Dict[str, Any],
                            detection_latency: float, camera_trigger_time: float) -> Tuple[bool, List[str]]:
        """Analyze test results against scenario requirements"""
        errors = []
        
        # Check detection latency
        max_latency = scenario.timing_requirements["max_detection_latency_ms"]
        if detection_latency > max_latency:
            errors.append(f"Detection latency {detection_latency:.1f}ms exceeds limit {max_latency}ms")
        
        # Check camera trigger latency
        max_trigger_latency = scenario.timing_requirements["max_camera_trigger_us"]
        if camera_trigger_time > max_trigger_latency:
            errors.append(f"Camera trigger {camera_trigger_time:.1f}µs exceeds limit {max_trigger_latency}µs")
        
        # Check signal ranges
        if raw_data["signal_measurements"]:
            for measurement in raw_data["signal_measurements"]:
                for i, (channel, value) in enumerate(zip(measurement["channels"], measurement["values"])):
                    channel_name = f"AIN{channel}"
                    if channel_name in scenario.expected_signals:
                        min_val, max_val = scenario.expected_signals[channel_name]
                        if not (min_val <= value <= max_val):
                            errors.append(f"{channel_name} value {value:.3f}V out of range [{min_val}, {max_val}]V")
        
        # Check VRU detection
        if raw_data["detection_events"]:
            detection = raw_data["detection_events"][0]
            if detection and detection["detected"]:
                if detection["signal_strength"] < scenario.detection_threshold:
                    errors.append(f"VRU detection strength {detection['signal_strength']:.3f} below threshold {scenario.detection_threshold}")
        
        success = len(errors) == 0
        return success, errors
    
    def _calculate_signal_quality(self, scenario: TestScenario, 
                                raw_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate signal quality metrics"""
        signal_quality = {}
        
        if not raw_data["signal_measurements"]:
            return signal_quality
        
        # Calculate SNR and stability for each channel
        for channel_idx in range(4):
            channel_name = f"AIN{channel_idx}"
            values = []
            
            for measurement in raw_data["signal_measurements"]:
                if len(measurement["values"]) > channel_idx:
                    values.append(measurement["values"][channel_idx])
            
            if values:
                mean_val = np.mean(values)
                std_val = np.std(values)
                
                # Signal-to-noise ratio (assuming noise is standard deviation)
                snr = mean_val / std_val if std_val > 0 else float('inf')
                
                # Stability (coefficient of variation)
                stability = 1.0 - (std_val / mean_val) if mean_val > 0 else 0.0
                
                signal_quality[channel_name] = {
                    "snr": min(snr, 100.0),  # Cap at 100 for practical purposes
                    "stability": max(0.0, min(stability, 1.0)),
                    "mean": mean_val,
                    "std": std_val
                }
        
        return signal_quality
    
    def _calculate_timing_precision(self, timing_events: List[TimingEvent]) -> float:
        """Calculate timing precision from events"""
        if len(timing_events) < 2:
            return 0.0
        
        # Calculate jitter between consecutive events
        jitters = []
        for i in range(1, len(timing_events)):
            time_diff = abs(timing_events[i].precision_us - timing_events[i-1].precision_us)
            jitters.append(time_diff)
        
        return np.mean(jitters) if jitters else 0.0
    
    def _update_performance_stats(self, result: TestResult):
        """Update overall performance statistics"""
        self.performance_stats["tests_executed"] += 1
        
        if result.success:
            self.performance_stats["tests_passed"] += 1
        else:
            self.performance_stats["tests_failed"] += 1
        
        # Update running averages
        n = self.performance_stats["tests_executed"]
        
        # Detection latency average
        current_avg = self.performance_stats["avg_detection_latency_ms"]
        new_avg = ((current_avg * (n - 1)) + result.detection_latency_ms) / n
        self.performance_stats["avg_detection_latency_ms"] = new_avg
        
        # Camera trigger latency average
        current_avg = self.performance_stats["avg_camera_latency_us"]
        new_avg = ((current_avg * (n - 1)) + result.camera_trigger_latency_us) / n
        self.performance_stats["avg_camera_latency_us"] = new_avg
        
        # Timing accuracy average
        current_avg = self.performance_stats["timing_accuracy_us"]
        new_avg = ((current_avg * (n - 1)) + result.timing_precision_us) / n
        self.performance_stats["timing_accuracy_us"] = new_avg
    
    async def run_full_test_suite(self) -> Dict[str, Any]:
        """Run complete ADAS HIL test suite"""
        self.logger.info("Starting full ADAS HIL test suite...")
        
        suite_start = time.perf_counter()
        suite_results = {
            "start_time": datetime.now().isoformat(),
            "scenarios": {},
            "summary": {},
            "performance": {},
            "issues": []
        }
        
        # Execute all scenarios
        for scenario_name in self.test_scenarios.keys():
            try:
                self.logger.info(f"Running scenario: {scenario_name}")
                results = await self.execute_test_scenario(scenario_name, iterations=3)
                
                # Analyze scenario results
                passed = sum(1 for r in results if r.success)
                avg_detection_latency = np.mean([r.detection_latency_ms for r in results])
                avg_camera_latency = np.mean([r.camera_trigger_latency_us for r in results])
                
                suite_results["scenarios"][scenario_name] = {
                    "results": [self._result_to_dict(r) for r in results],
                    "summary": {
                        "total": len(results),
                        "passed": passed,
                        "failed": len(results) - passed,
                        "success_rate": passed / len(results),
                        "avg_detection_latency_ms": avg_detection_latency,
                        "avg_camera_latency_us": avg_camera_latency
                    }
                }
                
                if passed < len(results):
                    suite_results["issues"].append(f"Scenario '{scenario_name}' had {len(results) - passed} failures")
                
            except Exception as e:
                self.logger.error(f"Scenario '{scenario_name}' execution failed: {e}")
                suite_results["issues"].append(f"Scenario '{scenario_name}' execution failed: {str(e)}")
        
        # Generate overall summary
        suite_duration = (time.perf_counter() - suite_start) * 1000
        
        suite_results["summary"] = {
            "duration_ms": suite_duration,
            "total_scenarios": len(self.test_scenarios),
            "scenarios_executed": len(suite_results["scenarios"]),
            "overall_success_rate": self._calculate_overall_success_rate(suite_results["scenarios"]),
            "total_tests": self.performance_stats["tests_executed"],
            "total_passed": self.performance_stats["tests_passed"],
            "total_failed": self.performance_stats["tests_failed"]
        }
        
        # Include performance metrics
        suite_results["performance"] = {
            **self.performance_stats,
            "labjack_metrics": self.labjack.get_performance_metrics()
        }
        
        suite_results["end_time"] = datetime.now().isoformat()
        
        self.logger.info(f"Test suite completed in {suite_duration:.1f}ms")
        self.logger.info(f"Overall success rate: {suite_results['summary']['overall_success_rate']:.1%}")
        
        return suite_results
    
    def _result_to_dict(self, result: TestResult) -> Dict[str, Any]:
        """Convert TestResult to dictionary for serialization"""
        return {
            "scenario_name": result.scenario.name,
            "timestamp": result.timestamp.isoformat(),
            "duration_ms": result.duration_ms,
            "detection_latency_ms": result.detection_latency_ms,
            "camera_trigger_latency_us": result.camera_trigger_latency_us,
            "signal_quality": result.signal_quality,
            "timing_precision_us": result.timing_precision_us,
            "success": result.success,
            "errors": result.errors
        }
    
    def _calculate_overall_success_rate(self, scenario_results: Dict[str, Any]) -> float:
        """Calculate overall success rate across all scenarios"""
        total_tests = 0
        total_passed = 0
        
        for scenario_data in scenario_results.values():
            if "summary" in scenario_data:
                total_tests += scenario_data["summary"]["total"]
                total_passed += scenario_data["summary"]["passed"]
        
        return total_passed / total_tests if total_tests > 0 else 0.0
    
    def get_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        return {
            "platform_info": {
                "labjack_device": self.labjack.device_info,
                "test_scenarios": {name: {
                    "name": s.name,
                    "description": s.description,
                    "vru_type": s.vru_type,
                    "detection_threshold": s.detection_threshold
                } for name, s in self.test_scenarios.items()}
            },
            "performance_stats": self.performance_stats,
            "recent_results": [self._result_to_dict(r) for r in self.test_results[-10:]],
            "hardware_metrics": self.labjack.get_performance_metrics()
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        self.labjack.disconnect()
        self.logger.info("ADAS HIL Testing Platform cleanup completed")

# Example usage and test runner
async def main():
    """Main test runner"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Initialize HIL tester
    tester = AdasHilTester()
    
    try:
        # Initialize platform
        if not await tester.initialize():
            print("Failed to initialize HIL testing platform")
            return
        
        # Run full test suite
        results = await tester.run_full_test_suite()
        
        # Print summary
        print("\n" + "="*80)
        print("ADAS HIL TESTING RESULTS SUMMARY")
        print("="*80)
        
        summary = results["summary"]
        print(f"Test Duration: {summary['duration_ms']:.1f}ms")
        print(f"Scenarios: {summary['scenarios_executed']}/{summary['total_scenarios']}")
        print(f"Tests: {summary['total_passed']}/{summary['total_tests']} passed")
        print(f"Success Rate: {summary['overall_success_rate']:.1%}")
        
        if results["issues"]:
            print(f"\nIssues Detected: {len(results['issues'])}")
            for issue in results["issues"]:
                print(f"  - {issue}")
        
        print("\nPerformance Metrics:")
        perf = results["performance"]
        print(f"  Average Detection Latency: {perf['avg_detection_latency_ms']:.1f}ms")
        print(f"  Average Camera Trigger: {perf['avg_camera_latency_us']:.1f}µs")
        print(f"  Timing Accuracy: {perf['timing_accuracy_us']:.1f}µs")
        
        # Save detailed results
        with open('/home/rigade/Testing/docs/adas_hil_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nDetailed results saved to: /home/rigade/Testing/docs/adas_hil_test_results.json")
        
    except Exception as e:
        print(f"Test execution failed: {e}")
    
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())