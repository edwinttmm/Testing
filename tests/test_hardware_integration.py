"""
Hardware Integration Tests for LabJack T7
Tests actual hardware connectivity, performance, and integration scenarios
"""

import pytest
import time
import asyncio
import threading
import numpy as np
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from labjack_t7_manager import LabJackT7Manager, LabJackConfig
from adas_hil_integration import AdasHilTester

# Hardware tests require actual LabJack T7 connection
pytestmark = pytest.mark.skipif(
    not os.environ.get("LABJACK_HARDWARE_TESTS"),
    reason="Hardware tests require LABJACK_HARDWARE_TESTS=1 and actual hardware"
)

class TestLabJackHardware:
    """Test actual LabJack T7 hardware functionality"""
    
    @pytest.fixture(scope="class")
    def manager(self):
        """Hardware manager fixture"""
        config = LabJackConfig()
        mgr = LabJackT7Manager(config)
        
        # Connect to actual hardware
        if mgr.connect():
            yield mgr
            mgr.disconnect()
        else:
            pytest.skip("Could not connect to LabJack T7 hardware")
    
    def test_hardware_connection(self, manager):
        """Test connection to actual hardware"""
        assert manager.connected
        assert manager.handle is not None
        assert "mock" not in manager.device_info
        assert manager.device_info["device_type"] == "T7"
        
        # Verify device info
        info = manager.device_info
        assert "serial_number" in info
        assert "firmware_version" in info
        assert "hardware_version" in info
        assert info["serial_number"] > 0
    
    def test_analog_input_reading(self, manager):
        """Test actual analog input reading"""
        result = manager.read_analog_precise([0, 1, 2, 3])
        
        assert len(result["values"]) == 1
        assert len(result["values"][0]) == 4
        assert result["read_time_us"] > 0
        assert result["read_time_us"] < 5000  # Should be under 5ms
        
        # Values should be within reasonable range (±10V)
        for value in result["values"][0]:
            assert -12.0 <= value <= 12.0
    
    def test_timing_precision(self, manager):
        """Test timing precision with actual hardware"""
        latencies = []
        num_tests = 50
        
        for _ in range(num_tests):
            start = time.perf_counter()
            manager.read_analog_precise([0])
            latency = (time.perf_counter() - start) * 1e6
            latencies.append(latency)
        
        avg_latency = np.mean(latencies)
        std_latency = np.std(latencies)
        max_latency = np.max(latencies)
        min_latency = np.min(latencies)
        
        print(f"\nTiming Analysis (Hardware):")
        print(f"  Average latency: {avg_latency:.1f}µs")
        print(f"  Std deviation: {std_latency:.1f}µs")
        print(f"  Min latency: {min_latency:.1f}µs")
        print(f"  Max latency: {max_latency:.1f}µs")
        print(f"  Jitter (CV): {std_latency/avg_latency*100:.1f}%")
        
        # Hardware should be faster and more consistent than mock
        assert avg_latency < 2000  # Less than 2ms average
        assert max_latency < 10000  # Less than 10ms max
        assert std_latency < avg_latency  # Reasonable jitter
    
    def test_gpio_trigger_operations(self, manager):
        """Test GPIO trigger operations on hardware"""
        # Test various pulse widths
        pulse_widths = [10, 50, 100, 200, 500]  # microseconds
        
        for pulse_width in pulse_widths:
            start_time = time.perf_counter()
            success = manager.trigger_camera_capture(pulse_width)
            end_time = time.perf_counter()
            
            actual_duration = (end_time - start_time) * 1e6
            
            assert success
            # Should complete within reasonable time (allow some overhead)
            assert actual_duration >= pulse_width
            assert actual_duration < pulse_width * 5  # Max 5x overhead
            
            print(f"Pulse {pulse_width}µs: actual {actual_duration:.1f}µs")
    
    def test_continuous_data_acquisition(self, manager):
        """Test continuous data acquisition performance"""
        # Acquire data for 1 second at high rate
        duration_s = 1.0
        sample_interval_ms = 1  # 1ms = 1000 Hz
        
        start_time = time.perf_counter()
        samples = []
        
        while (time.perf_counter() - start_time) < duration_s:
            sample_start = time.perf_counter()
            result = manager.read_analog_precise([0, 1])
            sample_time = (time.perf_counter() - sample_start) * 1000
            
            samples.append({
                "values": result["values"][0],
                "latency_ms": sample_time,
                "timestamp": time.perf_counter()
            })
            
            # Maintain sample rate
            time.sleep(sample_interval_ms / 1000.0)
        
        total_samples = len(samples)
        actual_rate = total_samples / duration_s
        avg_latency = np.mean([s["latency_ms"] for s in samples])
        max_latency = np.max([s["latency_ms"] for s in samples])
        
        print(f"\nContinuous Acquisition Results:")
        print(f"  Target rate: {1000/sample_interval_ms:.0f} Hz")
        print(f"  Actual rate: {actual_rate:.0f} Hz")
        print(f"  Total samples: {total_samples}")
        print(f"  Average latency: {avg_latency:.2f}ms")
        print(f"  Maximum latency: {max_latency:.2f}ms")
        
        # Verify performance
        assert total_samples >= (duration_s * 1000 / sample_interval_ms * 0.9)  # At least 90% of target
        assert avg_latency < sample_interval_ms  # Latency should be less than sample interval
        assert max_latency < sample_interval_ms * 2  # Max latency reasonable
    
    def test_streaming_performance(self, manager):
        """Test streaming mode performance"""
        channels = ["AIN0", "AIN1", "AIN2", "AIN3"]
        scan_rate = 1000  # Hz
        
        # Start streaming
        success = manager.start_streaming(channels, scan_rate)
        assert success
        assert manager.streaming
        
        # Let it stream for a short time
        time.sleep(0.5)
        
        # Stop streaming
        manager.stop_streaming()
        assert not manager.streaming
        
        print("Streaming test completed successfully")
    
    def test_signal_integrity(self, manager):
        """Test signal integrity and noise levels"""
        # Read multiple samples to analyze noise
        num_samples = 100
        result = manager.read_analog_precise([0, 1, 2, 3], num_samples=num_samples)
        
        assert len(result["values"]) == num_samples
        
        # Analyze each channel
        for ch_idx in range(4):
            channel_values = [sample[ch_idx] for sample in result["values"]]
            
            mean_val = np.mean(channel_values)
            std_val = np.std(channel_values)
            
            # Calculate SNR (simple approximation)
            snr = abs(mean_val) / std_val if std_val > 0 else float('inf')
            
            print(f"AIN{ch_idx}: Mean={mean_val:.4f}V, Std={std_val:.4f}V, SNR={snr:.1f}")
            
            # Basic signal integrity checks
            assert std_val < 0.1  # Noise should be low
            assert -10.5 <= mean_val <= 10.5  # Within expected range
    
    def test_concurrent_hardware_operations(self, manager):
        """Test concurrent operations on hardware"""
        results = []
        errors = []
        num_threads = 3
        operations_per_thread = 20
        
        def worker(thread_id):
            try:
                for i in range(operations_per_thread):
                    # Mix of read and trigger operations
                    if i % 3 == 0:
                        success = manager.trigger_camera_capture(100)
                        results.append(f"T{thread_id}-trigger-{i}: {success}")
                    else:
                        result = manager.read_analog_precise([thread_id % 4])
                        results.append(f"T{thread_id}-read-{i}: {len(result['values'])}")
                    
                    time.sleep(0.001)  # Small delay
                    
            except Exception as e:
                errors.append(f"Thread {thread_id} error: {str(e)}")
        
        # Start threads
        threads = []
        start_time = time.perf_counter()
        
        for t in range(num_threads):
            thread = threading.Thread(target=worker, args=(t,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        print(f"\nConcurrent Operations Results:")
        print(f"  Threads: {num_threads}")
        print(f"  Operations per thread: {operations_per_thread}")
        print(f"  Total operations: {len(results)}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Operations/sec: {len(results)/total_time:.0f}")
        print(f"  Errors: {len(errors)}")
        
        # Verify results
        assert len(errors) == 0
        assert len(results) == num_threads * operations_per_thread
    
    def test_error_recovery(self, manager):
        """Test error recovery and reconnection"""
        # Store original handle
        original_handle = manager.handle
        
        # Simulate connection loss by clearing handle
        manager.handle = None
        manager.connected = False
        
        # This should trigger reconnection attempt
        with pytest.raises(RuntimeError):
            manager.read_analog_precise([0])
        
        # Check that error was recorded
        assert manager.performance_metrics["error_count"] > 0
        
        # Restore connection manually (simulating successful reconnection)
        manager.handle = original_handle
        manager.connected = True
        
        # Should work again
        result = manager.read_analog_precise([0])
        assert len(result["values"]) > 0


class TestAdasHilHardware:
    """Test ADAS HIL integration with actual hardware"""
    
    @pytest.fixture(scope="class")
    def hil_tester(self):
        """HIL tester fixture"""
        tester = AdasHilTester()
        
        # Initialize with hardware
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            success = loop.run_until_complete(tester.initialize())
            if success:
                yield tester
            else:
                pytest.skip("Could not initialize HIL tester with hardware")
        finally:
            loop.run_until_complete(tester.cleanup())
            loop.close()
    
    @pytest.mark.asyncio
    async def test_hil_initialization(self, hil_tester):
        """Test HIL platform initialization with hardware"""
        assert hil_tester.labjack.connected
        assert len(hil_tester.test_scenarios) >= 3
        assert hasattr(hil_tester, 'baseline_signals')
        
        # Check baseline signals were established
        for channel in ["AIN0", "AIN1", "AIN2", "AIN3"]:
            assert channel in hil_tester.baseline_signals
            baseline = hil_tester.baseline_signals[channel]
            assert "mean" in baseline
            assert "std" in baseline
    
    @pytest.mark.asyncio
    async def test_single_scenario_execution(self, hil_tester):
        """Test execution of single test scenario"""
        scenario_name = "pedestrian_crossing"
        results = await hil_tester.execute_test_scenario(scenario_name, iterations=1)
        
        assert len(results) == 1
        result = results[0]
        
        assert result.scenario.name == scenario_name
        assert result.duration_ms > 0
        assert result.camera_trigger_latency_us > 0
        assert isinstance(result.success, bool)
        assert isinstance(result.errors, list)
        assert len(result.raw_data) > 0
        
        # Check timing requirements
        max_trigger_latency = result.scenario.timing_requirements["max_camera_trigger_us"]
        if result.success:
            assert result.camera_trigger_latency_us <= max_trigger_latency
    
    @pytest.mark.asyncio
    async def test_multiple_scenarios(self, hil_tester):
        """Test multiple scenario execution"""
        all_results = []
        
        for scenario_name in ["pedestrian_crossing", "cyclist_approach"]:
            results = await hil_tester.execute_test_scenario(scenario_name, iterations=2)
            all_results.extend(results)
        
        assert len(all_results) == 4
        
        # Check performance statistics were updated
        stats = hil_tester.performance_stats
        assert stats["tests_executed"] >= 4
        assert stats["avg_detection_latency_ms"] >= 0
        assert stats["avg_camera_latency_us"] > 0
    
    @pytest.mark.asyncio
    async def test_full_test_suite_hardware(self, hil_tester):
        """Test complete test suite with hardware"""
        suite_results = await hil_tester.run_full_test_suite()
        
        assert "start_time" in suite_results
        assert "end_time" in suite_results
        assert "scenarios" in suite_results
        assert "summary" in suite_results
        assert "performance" in suite_results
        
        summary = suite_results["summary"]
        assert summary["duration_ms"] > 0
        assert summary["total_scenarios"] >= 3
        assert summary["scenarios_executed"] >= 3
        assert 0 <= summary["overall_success_rate"] <= 1
        
        # Check performance metrics
        performance = suite_results["performance"]
        assert "labjack_metrics" in performance
        assert "avg_detection_latency_ms" in performance
        assert "avg_camera_latency_us" in performance
        
        print(f"\nFull Test Suite Results:")
        print(f"  Duration: {summary['duration_ms']:.1f}ms")
        print(f"  Scenarios: {summary['scenarios_executed']}/{summary['total_scenarios']}")
        print(f"  Success Rate: {summary['overall_success_rate']:.1%}")
        print(f"  Avg Detection Latency: {performance['avg_detection_latency_ms']:.1f}ms")
        print(f"  Avg Camera Latency: {performance['avg_camera_latency_us']:.1f}µs")


if __name__ == "__main__":
    # Set environment variable for hardware tests
    os.environ["LABJACK_HARDWARE_TESTS"] = "1"
    
    # Run hardware tests
    pytest.main([__file__, "-v", "-s"])