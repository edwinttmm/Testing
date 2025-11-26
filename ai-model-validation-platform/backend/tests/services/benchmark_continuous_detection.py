#!/usr/bin/env python3
"""
Performance benchmark script for continuous detection algorithm.
Measures CPU overhead, memory footprint, and throughput.
"""

import time
import psutil
import os
import sys
from typing import Dict, List
from unittest.mock import MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from services.dedicated_labjack_monitor import LabJackMonitoringServiceEnhanced


class PerformanceBenchmark:
    """Performance benchmark suite"""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.results: List[Dict] = []

    def benchmark_scenario(self,
                          name: str,
                          continuous_mode: bool,
                          min_interval_ms: float,
                          test_duration_s: float,
                          pulse_pattern: str):
        """
        Run a single benchmark scenario.

        Args:
            name: Scenario name
            continuous_mode: Enable continuous detection
            min_interval_ms: Minimum interval between detections
            test_duration_s: Duration of test in seconds
            pulse_pattern: Voltage pattern ("sustained_high", "pulses", "noise")
        """
        print(f"\n{'='*60}")
        print(f"Benchmark: {name}")
        print(f"{'='*60}")
        print(f"Config: continuous={continuous_mode}, interval={min_interval_ms}ms")
        print(f"Duration: {test_duration_s}s, Pattern: {pulse_pattern}")

        # Create service
        service = LabJackMonitoringServiceEnhanced(
            min_interval_ms=min_interval_ms,
            enable_continuous_detection=continuous_mode
        )

        # Mock dependencies
        with patch('services.labjack_monitoring_service_enhanced.signal_validation_service') as mock_signal, \
             patch('services.labjack_monitoring_service_enhanced.sqlite3.connect') as mock_db:

            # Setup mocks
            mock_db.return_value = MagicMock()

            # Generate voltage pattern
            def voltage_generator():
                t = 0.0
                while True:
                    if pulse_pattern == "sustained_high":
                        voltage = 3.0
                    elif pulse_pattern == "pulses":
                        # 500ms on, 500ms off
                        voltage = 3.0 if (int(t) % 2 == 0) else 1.0
                    elif pulse_pattern == "noise":
                        # Rapid oscillation
                        voltage = 3.0 if (int(t * 100) % 2 == 0) else 1.0
                    else:
                        voltage = 1.0

                    yield {"success": True, "voltage": voltage}
                    t += 0.010  # 10ms increment

            gen = voltage_generator()
            mock_signal.read_voltage_signal.side_effect = lambda _: next(gen)

            # Measure baseline
            baseline_cpu = self.process.cpu_percent(interval=0.5)
            baseline_memory = self.process.memory_info().rss / 1024 / 1024  # MB

            # Start monitoring
            start_time = time.time()
            service.start_monitoring("benchmark-test", sample_rate=100)

            # Wait for test duration
            time.sleep(test_duration_s)

            # Measure during monitoring
            monitoring_cpu = self.process.cpu_percent(interval=0.5)
            monitoring_memory = self.process.memory_info().rss / 1024 / 1024  # MB

            # Stop monitoring
            service.stop_monitoring()
            end_time = time.time()

            # Collect metrics
            metrics = service.get_metrics()
            elapsed = end_time - start_time

            result = {
                "name": name,
                "continuous_mode": continuous_mode,
                "min_interval_ms": min_interval_ms,
                "pulse_pattern": pulse_pattern,
                "test_duration_s": elapsed,
                "baseline_cpu_pct": baseline_cpu,
                "monitoring_cpu_pct": monitoring_cpu,
                "cpu_overhead_pct": monitoring_cpu - baseline_cpu,
                "baseline_memory_mb": baseline_memory,
                "monitoring_memory_mb": monitoring_memory,
                "memory_overhead_mb": monitoring_memory - baseline_memory,
                "total_detections": metrics["total_detections"],
                "rising_edge_detections": metrics["rising_edge_detections"],
                "continuous_detections": metrics["continuous_detections"],
                "detections_per_second": metrics["total_detections"] / elapsed
            }

            self.results.append(result)

            # Print results
            print(f"\nResults:")
            print(f"  Elapsed time: {elapsed:.2f}s")
            print(f"  CPU: {baseline_cpu:.2f}% → {monitoring_cpu:.2f}% (overhead: {result['cpu_overhead_pct']:.2f}%)")
            print(f"  Memory: {baseline_memory:.1f}MB → {monitoring_memory:.1f}MB (overhead: {result['memory_overhead_mb']:.1f}MB)")
            print(f"  Total detections: {metrics['total_detections']}")
            print(f"    - Rising edge: {metrics['rising_edge_detections']}")
            print(f"    - Continuous: {metrics['continuous_detections']}")
            print(f"  Throughput: {result['detections_per_second']:.1f} detections/sec")

            # Success criteria
            success = (
                result['cpu_overhead_pct'] < 5.0 and
                result['memory_overhead_mb'] < 10.0
            )
            status = "PASS" if success else "FAIL"
            print(f"\nStatus: {status}")

            return result

    def run_all_benchmarks(self):
        """Run comprehensive benchmark suite"""
        print("\n" + "="*60)
        print("CONTINUOUS DETECTION PERFORMANCE BENCHMARK")
        print("="*60)

        # Scenario 1: Legacy mode (rising-edge only)
        self.benchmark_scenario(
            name="Legacy Mode - Pulses",
            continuous_mode=False,
            min_interval_ms=40,
            test_duration_s=5.0,
            pulse_pattern="pulses"
        )

        # Scenario 2: Continuous mode with 40ms interval (24fps)
        self.benchmark_scenario(
            name="Continuous Mode - Sustained High (40ms)",
            continuous_mode=True,
            min_interval_ms=40,
            test_duration_s=5.0,
            pulse_pattern="sustained_high"
        )

        # Scenario 3: Continuous mode with 20ms interval (50fps)
        self.benchmark_scenario(
            name="Continuous Mode - Sustained High (20ms)",
            continuous_mode=True,
            min_interval_ms=20,
            test_duration_s=5.0,
            pulse_pattern="sustained_high"
        )

        # Scenario 4: Continuous mode with 10ms interval (100fps)
        self.benchmark_scenario(
            name="Continuous Mode - Sustained High (10ms)",
            continuous_mode=True,
            min_interval_ms=10,
            test_duration_s=5.0,
            pulse_pattern="sustained_high"
        )

        # Scenario 5: Noisy signal handling
        self.benchmark_scenario(
            name="Continuous Mode - Noisy Signal",
            continuous_mode=True,
            min_interval_ms=40,
            test_duration_s=5.0,
            pulse_pattern="noise"
        )

        # Scenario 6: Real-world pattern (pulses with continuous detection)
        self.benchmark_scenario(
            name="Continuous Mode - Realistic Pulses",
            continuous_mode=True,
            min_interval_ms=40,
            test_duration_s=10.0,
            pulse_pattern="pulses"
        )

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)

        print(f"\n{'Scenario':<40} {'CPU%':<8} {'Mem(MB)':<10} {'Det/s':<10}")
        print("-" * 68)

        for result in self.results:
            print(
                f"{result['name']:<40} "
                f"{result['cpu_overhead_pct']:>6.2f}% "
                f"{result['memory_overhead_mb']:>8.1f} "
                f"{result['detections_per_second']:>9.1f}"
            )

        # Overall statistics
        avg_cpu = sum(r['cpu_overhead_pct'] for r in self.results) / len(self.results)
        max_cpu = max(r['cpu_overhead_pct'] for r in self.results)
        avg_mem = sum(r['memory_overhead_mb'] for r in self.results) / len(self.results)
        max_mem = max(r['memory_overhead_mb'] for r in self.results)

        print("\nOverall Statistics:")
        print(f"  Average CPU overhead: {avg_cpu:.2f}%")
        print(f"  Maximum CPU overhead: {max_cpu:.2f}%")
        print(f"  Average memory overhead: {avg_mem:.1f}MB")
        print(f"  Maximum memory overhead: {max_mem:.1f}MB")

        # Pass/Fail
        all_pass = all(
            r['cpu_overhead_pct'] < 5.0 and r['memory_overhead_mb'] < 10.0
            for r in self.results
        )

        print(f"\nFinal Result: {'PASS' if all_pass else 'FAIL'}")

        if not all_pass:
            print("\nFailed scenarios:")
            for result in self.results:
                if result['cpu_overhead_pct'] >= 5.0 or result['memory_overhead_mb'] >= 10.0:
                    print(f"  - {result['name']}")

    def export_results(self, filename: str):
        """Export results to CSV"""
        import csv

        with open(filename, 'w', newline='') as f:
            if not self.results:
                return

            writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
            writer.writeheader()
            writer.writerows(self.results)

        print(f"\nResults exported to: {filename}")


def main():
    """Run benchmark suite"""
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()
    benchmark.export_results("/home/rigade/Testing/ai-model-validation-platform/backend/docs/benchmark_results.csv")


if __name__ == "__main__":
    main()
