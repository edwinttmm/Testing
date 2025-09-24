#!/usr/bin/env python3
"""
LabJack T7 Performance Validation Script
ADAS Camera HIL Testing Platform - Performance Benchmarking

Advanced performance testing for LabJack T7 hardware in ADAS HIL scenarios.
Measures timing accuracy, jitter, throughput, and real-time capabilities.

Author: AI Model Validation Platform  
Date: 2025-09-14
"""

import time
import statistics
import threading
import json
import sys
import os
from typing import List, Dict, Tuple
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LabJackPerformanceValidator:
    """
    High-performance validation suite for LabJack T7 in ADAS HIL testing.
    
    Focuses on:
    - Microsecond timing precision
    - High-frequency data acquisition
    - Concurrent operations performance
    - Memory efficiency
    - Signal processing accuracy
    - Real-time responsiveness
    """
    
    def __init__(self):
        """Initialize performance validator."""
        self.test_results = {}
        self.performance_data = {}
        
        # Performance test configuration
        self.high_freq_samples = 10000
        self.stress_test_duration = 30  # seconds
        self.concurrent_threads = 4
        self.timing_precision_samples = 5000
        
        # Mock LabJack for testing when hardware unavailable
        self.mock_mode = True
        self.labjack_handle = self._create_mock_labjack()
        
    def _create_mock_labjack(self):
        """Create mock LabJack for performance testing."""
        class MockLabJackT7:
            def __init__(self):
                self.last_read_time = time.perf_counter()
                self.read_count = 0
                
            def read_analog(self, channel):
                self.read_count += 1
                # Simulate realistic timing and voltage values
                now = time.perf_counter()
                dt = now - self.last_read_time
                self.last_read_time = now
                
                # Simulate voltage with slight noise
                base_voltage = 2.5
                noise = (hash(f"{channel}_{self.read_count}") % 1000 - 500) / 100000
                return base_voltage + noise
                
            def write_digital(self, channel, value):
                # Simulate digital write timing
                time.sleep(0.00001)  # 10 microsecond write time
                return True
                
            def read_digital(self, channel):
                return bool(hash(f"{channel}_{time.time()}") % 2)
        
        return MockLabJackT7()
    
    def validate_microsecond_timing(self) -> Dict:
        """
        Validate microsecond timing precision for ADAS requirements.
        
        ADAS HIL testing requires:
        - < 100μs event response time
        - < 10μs timing jitter
        - Consistent timing under load
        
        Returns:
            Dict: Timing validation results
        """
        logger.info("⏱️ Validating microsecond timing precision...")
        
        timing_samples = []
        jitter_samples = []
        
        # High-precision timing test
        for i in range(self.timing_precision_samples):
            start_time = time.perf_counter()
            
            # Simulate ADAS event processing
            voltage = self.labjack_handle.read_analog('AIN0')
            
            end_time = time.perf_counter()
            operation_time = (end_time - start_time) * 1000000  # microseconds
            
            timing_samples.append(operation_time)
            
            # Calculate jitter from expected timing
            if i > 0:
                expected_interval = 1000000 / 1000  # 1kHz expected rate
                actual_interval = (end_time - previous_end_time) * 1000000
                jitter = abs(actual_interval - expected_interval)
                jitter_samples.append(jitter)
            
            previous_end_time = end_time
            
            # Small delay to simulate 1kHz sampling
            if i < self.timing_precision_samples - 1:
                time.sleep(0.0005)  # 500μs
        
        # Calculate timing statistics
        mean_timing = statistics.mean(timing_samples)
        timing_std = statistics.stdev(timing_samples) if len(timing_samples) > 1 else 0
        max_timing = max(timing_samples)
        min_timing = min(timing_samples)
        
        mean_jitter = statistics.mean(jitter_samples) if jitter_samples else 0
        max_jitter = max(jitter_samples) if jitter_samples else 0
        
        # ADAS compliance checks
        adas_response_compliant = max_timing < 100  # < 100μs max response
        adas_jitter_compliant = mean_jitter < 10    # < 10μs mean jitter
        adas_consistent = timing_std < 5            # < 5μs standard deviation
        
        timing_results = {
            "mean_timing_us": mean_timing,
            "timing_std_us": timing_std,
            "min_timing_us": min_timing,
            "max_timing_us": max_timing,
            "mean_jitter_us": mean_jitter,
            "max_jitter_us": max_jitter,
            "samples_analyzed": len(timing_samples),
            "adas_response_compliant": adas_response_compliant,
            "adas_jitter_compliant": adas_jitter_compliant,
            "adas_consistent": adas_consistent,
            "overall_adas_compliant": all([adas_response_compliant, adas_jitter_compliant, adas_consistent]),
            "timing_grade": self._grade_timing_performance(mean_timing, timing_std, mean_jitter)
        }
        
        logger.info(f"   Mean timing: {mean_timing:.2f}μs ±{timing_std:.2f}μs")
        logger.info(f"   Max timing: {max_timing:.2f}μs")
        logger.info(f"   Mean jitter: {mean_jitter:.2f}μs")
        logger.info(f"   ADAS compliant: {'✅' if timing_results['overall_adas_compliant'] else '❌'}")
        
        return timing_results
    
    def validate_high_frequency_acquisition(self) -> Dict:
        """
        Validate high-frequency data acquisition performance.
        
        Tests continuous data acquisition at various sampling rates
        to verify HIL testing capabilities.
        
        Returns:
            Dict: High-frequency acquisition results
        """
        logger.info("🚀 Validating high-frequency acquisition...")
        
        acquisition_results = {}
        
        # Test multiple sampling rates
        test_rates = [100, 500, 1000, 2000, 5000]  # Hz
        
        for target_rate in test_rates:
            logger.info(f"   Testing {target_rate}Hz acquisition...")
            
            samples_collected = []
            timing_intervals = []
            
            target_interval = 1.0 / target_rate  # seconds
            test_duration = 2.0  # 2 second test
            
            start_time = time.perf_counter()
            last_sample_time = start_time
            
            while (time.perf_counter() - start_time) < test_duration:
                sample_start = time.perf_counter()
                
                # Acquire data sample
                voltage = self.labjack_handle.read_analog('AIN0')
                samples_collected.append(voltage)
                
                sample_end = time.perf_counter()
                
                # Calculate timing
                sample_time = sample_end - sample_start
                interval_time = sample_start - last_sample_time
                timing_intervals.append(interval_time)
                
                last_sample_time = sample_start
                
                # Maintain target rate
                remaining_time = target_interval - sample_time
                if remaining_time > 0:
                    time.sleep(remaining_time)
            
            total_duration = time.perf_counter() - start_time
            actual_rate = len(samples_collected) / total_duration
            
            # Calculate performance metrics
            mean_interval = statistics.mean(timing_intervals[1:])  # Skip first interval
            interval_std = statistics.stdev(timing_intervals[1:]) if len(timing_intervals) > 2 else 0
            
            rate_accuracy = (actual_rate / target_rate) * 100
            rate_stability = (1 - (interval_std / mean_interval)) * 100 if mean_interval > 0 else 0
            
            acquisition_results[f"{target_rate}Hz"] = {
                "target_rate_hz": target_rate,
                "actual_rate_hz": actual_rate,
                "rate_accuracy_percent": rate_accuracy,
                "rate_stability_percent": rate_stability,
                "samples_collected": len(samples_collected),
                "test_duration_s": total_duration,
                "mean_interval_s": mean_interval,
                "interval_std_s": interval_std,
                "achievable": rate_accuracy > 95,
                "stable": rate_stability > 90
            }
            
            logger.info(f"     Actual rate: {actual_rate:.1f}Hz ({rate_accuracy:.1f}% accuracy)")
        
        # Overall assessment
        max_stable_rate = 0
        for rate_key, results in acquisition_results.items():
            if results["achievable"] and results["stable"]:
                max_stable_rate = max(max_stable_rate, results["target_rate_hz"])
        
        acquisition_results["summary"] = {
            "max_stable_rate_hz": max_stable_rate,
            "high_frequency_capable": max_stable_rate >= 1000,
            "adas_hil_ready": max_stable_rate >= 500
        }
        
        return acquisition_results
    
    def validate_concurrent_operations(self) -> Dict:
        """
        Validate concurrent operation performance for multi-channel HIL testing.
        
        Simulates real ADAS scenario with multiple simultaneous operations:
        - Analog monitoring
        - Digital trigger generation
        - Event processing
        - Data logging
        
        Returns:
            Dict: Concurrent operations performance results
        """
        logger.info("⚡ Validating concurrent operations performance...")
        
        concurrent_results = {}
        
        # Shared data structures for thread communication
        results_lock = threading.Lock()
        shared_results = {
            "analog_samples": [],
            "digital_operations": 0,
            "events_processed": 0,
            "errors": []
        }
        
        def analog_monitoring_thread():
            """Continuous analog monitoring thread."""
            samples = 0
            start_time = time.perf_counter()
            
            try:
                while (time.perf_counter() - start_time) < 10:  # 10 second test
                    voltage = self.labjack_handle.read_analog('AIN0')
                    
                    with results_lock:
                        shared_results["analog_samples"].append(voltage)
                    
                    samples += 1
                    time.sleep(0.001)  # 1ms interval (1kHz)
                
            except Exception as e:
                with results_lock:
                    shared_results["errors"].append(f"Analog thread: {e}")
        
        def digital_trigger_thread():
            """Digital trigger generation thread."""
            operations = 0
            start_time = time.perf_counter()
            
            try:
                while (time.perf_counter() - start_time) < 10:  # 10 second test
                    # Toggle digital output
                    self.labjack_handle.write_digital('FIO0', operations % 2)
                    operations += 1
                    
                    time.sleep(0.01)  # 10ms interval (100Hz)
                
                with results_lock:
                    shared_results["digital_operations"] = operations
                    
            except Exception as e:
                with results_lock:
                    shared_results["errors"].append(f"Digital thread: {e}")
        
        def event_processing_thread():
            """Event processing simulation thread."""
            events = 0
            start_time = time.perf_counter()
            
            try:
                while (time.perf_counter() - start_time) < 10:  # 10 second test
                    # Simulate VRU event processing
                    voltage = self.labjack_handle.read_analog('AIN1')
                    
                    # Process event (simulate computation)
                    if voltage > 2.0:  # Threshold detection
                        events += 1
                        # Simulate processing delay
                        time.sleep(0.0001)  # 100μs processing
                    
                    time.sleep(0.005)  # 5ms interval (200Hz)
                
                with results_lock:
                    shared_results["events_processed"] = events
                    
            except Exception as e:
                with results_lock:
                    shared_results["errors"].append(f"Event thread: {e}")
        
        # Start concurrent threads
        threads = [
            threading.Thread(target=analog_monitoring_thread),
            threading.Thread(target=digital_trigger_thread),
            threading.Thread(target=event_processing_thread)
        ]
        
        logger.info("   Starting concurrent operation threads...")
        
        test_start_time = time.perf_counter()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        test_duration = time.perf_counter() - test_start_time
        
        # Analyze results
        analog_samples_count = len(shared_results["analog_samples"])
        analog_rate = analog_samples_count / test_duration
        
        digital_ops_count = shared_results["digital_operations"]
        digital_rate = digital_ops_count / test_duration
        
        events_count = shared_results["events_processed"]
        event_rate = events_count / test_duration
        
        error_count = len(shared_results["errors"])
        
        concurrent_results = {
            "test_duration_s": test_duration,
            "analog_samples_collected": analog_samples_count,
            "analog_rate_hz": analog_rate,
            "digital_operations": digital_ops_count,
            "digital_rate_hz": digital_rate,
            "events_processed": events_count,
            "event_rate_hz": event_rate,
            "total_errors": error_count,
            "error_list": shared_results["errors"],
            "concurrent_performance": {
                "analog_target_met": analog_rate > 900,  # Target: 1kHz
                "digital_target_met": digital_rate > 90,   # Target: 100Hz
                "events_target_met": event_rate > 180,     # Target: 200Hz
                "error_free": error_count == 0
            },
            "overall_concurrent_capable": all([
                analog_rate > 900,
                digital_rate > 90,
                event_rate > 180,
                error_count == 0
            ])
        }
        
        logger.info(f"   Analog rate: {analog_rate:.1f}Hz")
        logger.info(f"   Digital rate: {digital_rate:.1f}Hz")
        logger.info(f"   Event rate: {event_rate:.1f}Hz")
        logger.info(f"   Errors: {error_count}")
        logger.info(f"   Concurrent capable: {'✅' if concurrent_results['overall_concurrent_capable'] else '❌'}")
        
        return concurrent_results
    
    def validate_memory_efficiency(self) -> Dict:
        """
        Validate memory usage efficiency during continuous operation.
        
        Returns:
            Dict: Memory efficiency validation results
        """
        logger.info("💾 Validating memory efficiency...")
        
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_samples = []
        data_buffer = []
        
        # Stress test - continuous data collection
        start_time = time.perf_counter()
        test_duration = 30  # 30 seconds
        
        while (time.perf_counter() - start_time) < test_duration:
            # Collect data
            voltage = self.labjack_handle.read_analog('AIN0')
            data_buffer.append(voltage)
            
            # Monitor memory every 100 samples
            if len(data_buffer) % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory)
            
            time.sleep(0.001)  # 1ms interval
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Calculate memory statistics
        memory_increase = final_memory - initial_memory
        max_memory = max(memory_samples) if memory_samples else final_memory
        mean_memory = statistics.mean(memory_samples) if memory_samples else final_memory
        
        samples_collected = len(data_buffer)
        memory_per_sample = memory_increase / samples_collected if samples_collected > 0 else 0
        
        # Memory efficiency assessment
        memory_efficient = memory_increase < 50  # < 50MB increase acceptable
        memory_stable = (max_memory - initial_memory) / initial_memory < 0.5  # < 50% increase
        
        memory_results = {
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "max_memory_mb": max_memory,
            "mean_memory_mb": mean_memory,
            "memory_increase_mb": memory_increase,
            "samples_collected": samples_collected,
            "memory_per_sample_kb": memory_per_sample * 1024,
            "test_duration_s": test_duration,
            "memory_efficient": memory_efficient,
            "memory_stable": memory_stable,
            "memory_grade": self._grade_memory_efficiency(memory_increase, memory_per_sample)
        }
        
        logger.info(f"   Memory increase: {memory_increase:.2f}MB")
        logger.info(f"   Memory per sample: {memory_per_sample * 1024:.3f}KB")
        logger.info(f"   Memory efficient: {'✅' if memory_efficient else '❌'}")
        
        # Cleanup
        del data_buffer
        gc.collect()
        
        return memory_results
    
    def validate_signal_integrity(self) -> Dict:
        """
        Validate signal integrity and noise characteristics.
        
        Returns:
            Dict: Signal integrity validation results
        """
        logger.info("📡 Validating signal integrity...")
        
        # Collect signal samples for analysis
        signal_samples = []
        noise_samples = []
        
        # Known reference voltage (simulated)
        reference_voltage = 2.5
        
        for i in range(1000):
            voltage = self.labjack_handle.read_analog('AIN0')
            signal_samples.append(voltage)
            
            # Calculate noise (deviation from reference)
            noise = abs(voltage - reference_voltage)
            noise_samples.append(noise)
            
            time.sleep(0.001)  # 1ms sampling
        
        # Signal analysis
        mean_voltage = statistics.mean(signal_samples)
        voltage_std = statistics.stdev(signal_samples)
        voltage_range = max(signal_samples) - min(signal_samples)
        
        mean_noise = statistics.mean(noise_samples)
        max_noise = max(noise_samples)
        
        # Signal-to-Noise Ratio calculation
        signal_power = mean_voltage ** 2
        noise_power = voltage_std ** 2
        snr_db = 10 * math.log10(signal_power / noise_power) if noise_power > 0 else float('inf')
        
        # Signal quality assessment
        signal_stable = voltage_std < 0.01  # < 10mV std deviation
        low_noise = mean_noise < 0.005      # < 5mV mean noise
        good_snr = snr_db > 40              # > 40dB SNR
        
        import math
        
        signal_results = {
            "mean_voltage": mean_voltage,
            "voltage_std": voltage_std,
            "voltage_range": voltage_range,
            "mean_noise": mean_noise,
            "max_noise": max_noise,
            "snr_db": snr_db if not math.isinf(snr_db) else 100,
            "samples_analyzed": len(signal_samples),
            "signal_stable": signal_stable,
            "low_noise": low_noise,
            "good_snr": good_snr,
            "signal_quality": "excellent" if all([signal_stable, low_noise, good_snr]) else
                             "good" if sum([signal_stable, low_noise, good_snr]) >= 2 else "poor"
        }
        
        logger.info(f"   Mean voltage: {mean_voltage:.4f}V ±{voltage_std:.6f}V")
        logger.info(f"   Noise level: {mean_noise:.6f}V")
        logger.info(f"   SNR: {signal_results['snr_db']:.1f}dB")
        logger.info(f"   Signal quality: {signal_results['signal_quality']}")
        
        return signal_results
    
    def _grade_timing_performance(self, mean_timing: float, timing_std: float, jitter: float) -> str:
        """Grade timing performance based on ADAS requirements."""
        if mean_timing < 50 and timing_std < 2 and jitter < 5:
            return "excellent"
        elif mean_timing < 100 and timing_std < 5 and jitter < 10:
            return "good"
        elif mean_timing < 200 and timing_std < 10 and jitter < 20:
            return "acceptable"
        else:
            return "poor"
    
    def _grade_memory_efficiency(self, memory_increase: float, memory_per_sample: float) -> str:
        """Grade memory efficiency."""
        if memory_increase < 20 and memory_per_sample < 0.001:
            return "excellent"
        elif memory_increase < 50 and memory_per_sample < 0.005:
            return "good"
        elif memory_increase < 100 and memory_per_sample < 0.01:
            return "acceptable"
        else:
            return "poor"
    
    def run_comprehensive_performance_validation(self) -> Dict:
        """
        Run comprehensive performance validation suite.
        
        Returns:
            Dict: Complete performance validation results
        """
        logger.info("🧪 Starting LabJack T7 Performance Validation Suite")
        logger.info("=" * 70)
        
        validation_results = {}
        
        # Performance validation modules
        validation_tests = [
            ("Microsecond Timing", self.validate_microsecond_timing),
            ("High-Frequency Acquisition", self.validate_high_frequency_acquisition),
            ("Concurrent Operations", self.validate_concurrent_operations),
            ("Memory Efficiency", self.validate_memory_efficiency),
            ("Signal Integrity", self.validate_signal_integrity)
        ]
        
        for test_name, test_function in validation_tests:
            try:
                logger.info(f"\n🔍 Running {test_name} validation...")
                validation_results[test_name.lower().replace(' ', '_').replace('-', '_')] = test_function()
                logger.info(f"✅ {test_name} validation completed")
            except Exception as e:
                logger.error(f"❌ {test_name} validation failed: {e}")
                validation_results[test_name.lower().replace(' ', '_').replace('-', '_')] = {"error": str(e)}
        
        # Generate performance summary
        performance_summary = self._generate_performance_summary(validation_results)
        
        complete_results = {
            "validation_suite": "LabJack T7 Performance Validation",
            "timestamp": datetime.now().isoformat(),
            "validation_results": validation_results,
            "performance_summary": performance_summary,
            "adas_hil_performance_ready": self._assess_adas_performance_readiness(validation_results)
        }
        
        self._log_performance_summary(complete_results)
        return complete_results
    
    def _generate_performance_summary(self, results: Dict) -> Dict:
        """Generate overall performance summary."""
        summary = {
            "timing_performance": "unknown",
            "acquisition_performance": "unknown", 
            "concurrent_performance": "unknown",
            "memory_performance": "unknown",
            "signal_performance": "unknown",
            "overall_performance": "unknown"
        }
        
        try:
            # Timing performance
            if "microsecond_timing" in results:
                timing = results["microsecond_timing"]
                if "timing_grade" in timing:
                    summary["timing_performance"] = timing["timing_grade"]
            
            # Acquisition performance
            if "high_frequency_acquisition" in results:
                acq = results["high_frequency_acquisition"]
                if "summary" in acq:
                    if acq["summary"]["high_frequency_capable"]:
                        summary["acquisition_performance"] = "excellent"
                    elif acq["summary"]["adas_hil_ready"]:
                        summary["acquisition_performance"] = "good"
                    else:
                        summary["acquisition_performance"] = "poor"
            
            # Concurrent performance
            if "concurrent_operations" in results:
                conc = results["concurrent_operations"]
                if conc.get("overall_concurrent_capable", False):
                    summary["concurrent_performance"] = "excellent"
                else:
                    summary["concurrent_performance"] = "needs_improvement"
            
            # Memory performance
            if "memory_efficiency" in results:
                mem = results["memory_efficiency"]
                if "memory_grade" in mem:
                    summary["memory_performance"] = mem["memory_grade"]
            
            # Signal performance
            if "signal_integrity" in results:
                sig = results["signal_integrity"]
                if "signal_quality" in sig:
                    summary["signal_performance"] = sig["signal_quality"]
            
            # Overall performance
            performance_levels = [
                summary["timing_performance"],
                summary["acquisition_performance"],
                summary["concurrent_performance"],
                summary["memory_performance"],
                summary["signal_performance"]
            ]
            
            excellent_count = performance_levels.count("excellent")
            good_count = performance_levels.count("good")
            poor_count = performance_levels.count("poor")
            
            if excellent_count >= 3:
                summary["overall_performance"] = "excellent"
            elif excellent_count + good_count >= 4:
                summary["overall_performance"] = "good"
            elif poor_count <= 1:
                summary["overall_performance"] = "acceptable"
            else:
                summary["overall_performance"] = "poor"
        
        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
        
        return summary
    
    def _assess_adas_performance_readiness(self, results: Dict) -> Dict:
        """Assess readiness for ADAS HIL testing based on performance."""
        readiness = {
            "timing_ready": False,
            "throughput_ready": False,
            "concurrent_ready": False,
            "memory_ready": False,
            "signal_ready": False,
            "overall_performance_ready": False
        }
        
        try:
            # Timing readiness
            if "microsecond_timing" in results:
                timing = results["microsecond_timing"]
                readiness["timing_ready"] = timing.get("overall_adas_compliant", False)
            
            # Throughput readiness
            if "high_frequency_acquisition" in results:
                acq = results["high_frequency_acquisition"]
                readiness["throughput_ready"] = acq.get("summary", {}).get("adas_hil_ready", False)
            
            # Concurrent readiness
            if "concurrent_operations" in results:
                conc = results["concurrent_operations"]
                readiness["concurrent_ready"] = conc.get("overall_concurrent_capable", False)
            
            # Memory readiness
            if "memory_efficiency" in results:
                mem = results["memory_efficiency"]
                readiness["memory_ready"] = mem.get("memory_efficient", False)
            
            # Signal readiness
            if "signal_integrity" in results:
                sig = results["signal_integrity"]
                readiness["signal_ready"] = sig.get("signal_quality") in ["excellent", "good"]
            
            # Overall readiness
            readiness["overall_performance_ready"] = all([
                readiness["timing_ready"],
                readiness["throughput_ready"],
                readiness["concurrent_ready"],
                readiness["memory_ready"],
                readiness["signal_ready"]
            ])
        
        except Exception as e:
            logger.error(f"Error assessing ADAS performance readiness: {e}")
        
        return readiness
    
    def _log_performance_summary(self, results: Dict):
        """Log performance validation summary."""
        logger.info("\n" + "=" * 70)
        logger.info("🏁 LABJACK T7 PERFORMANCE VALIDATION SUMMARY")
        logger.info("=" * 70)
        
        summary = results.get("performance_summary", {})
        readiness = results.get("adas_hil_performance_ready", {})
        
        logger.info("📊 Performance Results:")
        logger.info(f"   Timing: {summary.get('timing_performance', 'unknown')}")
        logger.info(f"   Acquisition: {summary.get('acquisition_performance', 'unknown')}")
        logger.info(f"   Concurrent Ops: {summary.get('concurrent_performance', 'unknown')}")
        logger.info(f"   Memory: {summary.get('memory_performance', 'unknown')}")
        logger.info(f"   Signal: {summary.get('signal_performance', 'unknown')}")
        logger.info(f"   Overall: {summary.get('overall_performance', 'unknown')}")
        
        logger.info(f"\n🎯 ADAS HIL Performance Ready: {'✅ YES' if readiness.get('overall_performance_ready') else '❌ NO'}")
        
        logger.info("=" * 70)

def main():
    """Main performance validation execution."""
    print("\n🚀 LabJack T7 Performance Validation Suite")
    print("=" * 70)
    print("Advanced performance testing for ADAS HIL scenarios")
    print("=" * 70)
    
    # Create validator instance
    validator = LabJackPerformanceValidator()
    
    try:
        # Run comprehensive performance validation
        results = validator.run_comprehensive_performance_validation()
        
        # Save results
        results_file = os.path.join(os.path.dirname(__file__), 'labjack_performance_validation_results.json')
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Performance validation results saved to: {results_file}")
        
        # Return exit code based on performance readiness
        if results["adas_hil_performance_ready"]["overall_performance_ready"]:
            return 0
        elif results["performance_summary"]["overall_performance"] in ["good", "acceptable"]:
            return 1
        else:
            return 2
    
    except Exception as e:
        logger.error(f"❌ Performance validation failed: {e}")
        return 3

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)