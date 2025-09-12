#!/usr/bin/env python3
"""
Timing Precision Validation Test Suite
Tests timing accuracy, synchronization, and performance metrics.
"""

import pytest
import time
import threading
import asyncio
from typing import List, Dict, Any
import statistics
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestTimingPrecision:
    """Test suite for timing precision validation."""
    
    def setup_class(self):
        """Setup timing test configuration."""
        self.timing_samples = 100
        self.precision_threshold_ms = 10  # 10ms precision requirement
        self.jitter_threshold_ms = 5      # 5ms jitter tolerance
        
        print(f"🔧 Timing precision requirements: {self.precision_threshold_ms}ms precision, {self.jitter_threshold_ms}ms jitter")
    
    def measure_timing_precision(self, iterations: int = 100) -> Dict[str, float]:
        """Measure timing precision over multiple iterations."""
        timings = []
        
        for i in range(iterations):
            start = time.perf_counter()
            
            # Simulate a minimal operation
            time.sleep(0.001)  # 1ms sleep
            
            end = time.perf_counter()
            elapsed_ms = (end - start) * 1000
            timings.append(elapsed_ms)
        
        return {
            'mean': statistics.mean(timings),
            'median': statistics.median(timings), 
            'std_dev': statistics.stdev(timings),
            'min': min(timings),
            'max': max(timings),
            'samples': len(timings)
        }
    
    def test_basic_timing_precision(self):
        """Test basic timing measurement precision."""
        print("🕐 Testing basic timing precision...")
        
        timing_stats = self.measure_timing_precision(self.timing_samples)
        
        # Check if timing is within acceptable range
        mean_timing = timing_stats['mean']
        std_dev = timing_stats['std_dev']
        
        assert mean_timing > 0.5, f"Mean timing too low: {mean_timing:.2f}ms"
        assert mean_timing < 10, f"Mean timing too high: {mean_timing:.2f}ms"
        assert std_dev < self.jitter_threshold_ms, f"Standard deviation too high: {std_dev:.2f}ms"
        
        print(f"✅ Basic timing precision test passed:")
        print(f"   Mean: {mean_timing:.2f}ms, StdDev: {std_dev:.2f}ms")
        print(f"   Range: {timing_stats['min']:.2f}ms - {timing_stats['max']:.2f}ms")
        
        return True
    
    def test_high_frequency_timing(self):
        """Test high-frequency timing measurements."""
        print("🚀 Testing high-frequency timing...")
        
        start_time = time.perf_counter()
        measurements = []
        
        # Take 1000 rapid measurements
        for i in range(1000):
            measurement_time = time.perf_counter()
            measurements.append(measurement_time)
        
        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000
        
        # Calculate intervals between measurements
        intervals = []
        for i in range(1, len(measurements)):
            interval = (measurements[i] - measurements[i-1]) * 1000  # Convert to ms
            intervals.append(interval)
        
        avg_interval = statistics.mean(intervals)
        interval_std = statistics.stdev(intervals) if len(intervals) > 1 else 0
        
        # High-frequency measurements should be consistent
        assert avg_interval < 1, f"Average interval too high: {avg_interval:.4f}ms"
        assert interval_std < 0.5, f"Interval jitter too high: {interval_std:.4f}ms"
        
        print(f"✅ High-frequency timing test passed:")
        print(f"   1000 measurements in {total_time:.2f}ms")
        print(f"   Average interval: {avg_interval:.4f}ms, Jitter: {interval_std:.4f}ms")
        
        return True
    
    def test_threading_timing_consistency(self):
        """Test timing consistency across multiple threads."""
        print("🧵 Testing threading timing consistency...")
        
        results = []
        threads = []
        
        def measure_thread_timing(thread_id: int):
            """Measure timing in a separate thread."""
            thread_timings = []
            
            for i in range(50):
                start = time.perf_counter()
                time.sleep(0.002)  # 2ms sleep
                end = time.perf_counter()
                elapsed = (end - start) * 1000
                thread_timings.append(elapsed)
            
            thread_stats = {
                'thread_id': thread_id,
                'mean': statistics.mean(thread_timings),
                'std_dev': statistics.stdev(thread_timings)
            }
            results.append(thread_stats)
        
        # Create 4 threads
        for i in range(4):
            thread = threading.Thread(target=measure_thread_timing, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Analyze cross-thread consistency
        thread_means = [result['mean'] for result in results]
        thread_stds = [result['std_dev'] for result in results]
        
        overall_mean = statistics.mean(thread_means)
        thread_consistency = statistics.stdev(thread_means)
        
        assert thread_consistency < 2, f"Thread timing inconsistency too high: {thread_consistency:.2f}ms"
        
        print(f"✅ Threading timing consistency test passed:")
        print(f"   Overall mean: {overall_mean:.2f}ms")
        print(f"   Thread consistency: {thread_consistency:.2f}ms")
        for result in results:
            print(f"   Thread {result['thread_id']}: {result['mean']:.2f}ms ±{result['std_dev']:.2f}ms")
        
        return True
    
    def test_async_timing_precision(self):
        """Test timing precision in async/await context."""
        print("⚡ Testing async timing precision...")
        
        async def measure_async_timing():
            timings = []
            
            for i in range(50):
                start = time.perf_counter()
                await asyncio.sleep(0.001)  # 1ms async sleep
                end = time.perf_counter()
                elapsed = (end - start) * 1000
                timings.append(elapsed)
            
            return {
                'mean': statistics.mean(timings),
                'std_dev': statistics.stdev(timings),
                'min': min(timings),
                'max': max(timings)
            }
        
        # Run async timing test
        async_stats = asyncio.run(measure_async_timing())
        
        # Async timing should be reasonably precise
        assert async_stats['mean'] > 0.5, f"Async mean timing too low: {async_stats['mean']:.2f}ms"
        assert async_stats['std_dev'] < 10, f"Async timing jitter too high: {async_stats['std_dev']:.2f}ms"
        
        print(f"✅ Async timing precision test passed:")
        print(f"   Mean: {async_stats['mean']:.2f}ms, StdDev: {async_stats['std_dev']:.2f}ms")
        print(f"   Range: {async_stats['min']:.2f}ms - {async_stats['max']:.2f}ms")
        
        return True
    
    def test_timestamp_synchronization(self):
        """Test timestamp synchronization accuracy."""
        print("🔄 Testing timestamp synchronization...")
        
        # Generate synchronized timestamps
        timestamps = []
        system_times = []
        
        for i in range(100):
            perf_time = time.perf_counter()
            sys_time = time.time()
            
            timestamps.append(perf_time)
            system_times.append(sys_time)
            
            time.sleep(0.001)  # Small delay
        
        # Calculate timestamp intervals
        perf_intervals = []
        sys_intervals = []
        
        for i in range(1, len(timestamps)):
            perf_interval = (timestamps[i] - timestamps[i-1]) * 1000
            sys_interval = (system_times[i] - system_times[i-1]) * 1000
            
            perf_intervals.append(perf_interval)
            sys_intervals.append(sys_interval)
        
        # Check synchronization consistency
        perf_mean = statistics.mean(perf_intervals)
        sys_mean = statistics.mean(sys_intervals)
        sync_diff = abs(perf_mean - sys_mean)
        
        assert sync_diff < 1, f"Timestamp synchronization drift too high: {sync_diff:.2f}ms"
        
        print(f"✅ Timestamp synchronization test passed:")
        print(f"   perf_counter mean: {perf_mean:.2f}ms")
        print(f"   time() mean: {sys_mean:.2f}ms")
        print(f"   Synchronization difference: {sync_diff:.2f}ms")
        
        return True
    
    def test_timing_under_load(self):
        """Test timing precision under system load."""
        print("🏋️  Testing timing precision under load...")
        
        # Create background load
        load_active = True
        
        def background_load():
            """Create CPU load in background."""
            counter = 0
            while load_active:
                counter += 1
                if counter % 10000 == 0:
                    time.sleep(0.0001)  # Brief pause
        
        # Start background load
        load_thread = threading.Thread(target=background_load)
        load_thread.daemon = True
        load_thread.start()
        
        try:
            # Measure timing under load
            load_timings = self.measure_timing_precision(50)
            
            # Stop background load
            load_active = False
            
            # Timing should still be reasonably precise under load
            assert load_timings['std_dev'] < self.jitter_threshold_ms * 2, f"Timing under load too inconsistent: {load_timings['std_dev']:.2f}ms"
            
            print(f"✅ Timing under load test passed:")
            print(f"   Mean: {load_timings['mean']:.2f}ms, StdDev: {load_timings['std_dev']:.2f}ms")
            
            return True
            
        finally:
            load_active = False
    
    def test_monotonic_timing(self):
        """Test monotonic timing characteristics."""
        print("📈 Testing monotonic timing...")
        
        timestamps = []
        
        # Collect monotonic timestamps
        for i in range(1000):
            timestamp = time.monotonic()
            timestamps.append(timestamp)
        
        # Check monotonicity
        non_monotonic_count = 0
        for i in range(1, len(timestamps)):
            if timestamps[i] <= timestamps[i-1]:
                non_monotonic_count += 1
        
        monotonic_percentage = ((len(timestamps) - 1 - non_monotonic_count) / (len(timestamps) - 1)) * 100
        
        assert monotonic_percentage > 99, f"Monotonic timing failure rate too high: {100-monotonic_percentage:.2f}%"
        
        print(f"✅ Monotonic timing test passed:")
        print(f"   Monotonic percentage: {monotonic_percentage:.2f}%")
        print(f"   Non-monotonic events: {non_monotonic_count}/{len(timestamps)-1}")
        
        return True

def run_timing_precision_validation():
    """Run all timing precision validation tests."""
    print("🔍 Starting Timing Precision Validation...")
    
    test_suite = TestTimingPrecision()
    test_suite.setup_class()
    
    tests = [
        test_suite.test_basic_timing_precision,
        test_suite.test_high_frequency_timing,
        test_suite.test_threading_timing_consistency,
        test_suite.test_async_timing_precision,
        test_suite.test_timestamp_synchronization,
        test_suite.test_timing_under_load,
        test_suite.test_monotonic_timing,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result if result is not None else True)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n📊 Timing Precision Validation Complete: {success_rate:.1f}% success rate ({sum(results)}/{len(results)} tests passed)")
    
    return success_rate > 80

if __name__ == "__main__":
    run_timing_precision_validation()