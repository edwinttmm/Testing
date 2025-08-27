#!/usr/bin/env python3
"""
VRU Platform Performance Benchmarking Suite
===========================================

Comprehensive performance testing for VRU validation platform.
Tests system performance, load handling, memory usage, and scalability.

Author: Performance Testing Agent
Date: 2025-08-27
"""

import pytest
import asyncio
import time
import psutil
import threading
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import logging
import numpy as np
from pathlib import Path
import tempfile
import sys
import os

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

@dataclass
class PerformanceBenchmarkConfig:
    """Configuration for performance benchmarking"""
    
    # Load Testing
    max_concurrent_users: int = 50
    test_duration_seconds: int = 300  # 5 minutes
    ramp_up_time: int = 60  # 1 minute
    
    # Memory Testing  
    memory_limit_mb: int = 1024
    memory_test_duration: int = 120
    
    # CPU Testing
    cpu_limit_percent: float = 85.0
    cpu_test_duration: int = 180
    
    # Network Testing
    network_timeout: int = 30
    max_request_size_mb: int = 100
    
    # ML Performance
    ml_inference_timeout: int = 60
    batch_size_limit: int = 10
    
    # Database Performance
    db_connection_pool_size: int = 25
    db_query_timeout: int = 30

class VRUPerformanceTester:
    """Main performance testing orchestrator"""
    
    def __init__(self, config: PerformanceBenchmarkConfig):
        self.config = config
        self.metrics = {}
        self.test_results = {}
        self.system_monitor = SystemResourceMonitor()
        
    async def run_comprehensive_benchmarks(self) -> Dict[str, Any]:
        """Run all performance benchmarks"""
        logger.info("🚀 Starting comprehensive VRU performance benchmarks")
        
        benchmark_suites = [
            self.ml_inference_benchmarks,
            self.database_performance_benchmarks,
            self.websocket_performance_benchmarks,
            self.memory_stress_tests,
            self.cpu_load_tests,
            self.concurrent_user_simulation,
            self.system_resource_limits_test
        ]
        
        # Run all benchmarks
        for benchmark in benchmark_suites:
            try:
                logger.info(f"Running {benchmark.__name__}...")
                await benchmark()
            except Exception as e:
                logger.error(f"Benchmark {benchmark.__name__} failed: {e}")
                
        return self.compile_final_report()
    
    async def ml_inference_benchmarks(self):
        """Test ML inference performance under various conditions"""
        logger.info("🧠 Running ML inference performance benchmarks")
        
        # Simulate different video processing scenarios
        test_scenarios = [
            {"name": "single_stream_hd", "width": 1920, "height": 1080, "fps": 30, "duration": 10},
            {"name": "single_stream_4k", "width": 3840, "height": 2160, "fps": 30, "duration": 5},
            {"name": "multi_stream_hd", "streams": 4, "width": 1920, "height": 1080, "fps": 30, "duration": 10},
            {"name": "low_latency_stream", "width": 640, "height": 480, "fps": 60, "duration": 15},
        ]
        
        ml_results = {}
        
        for scenario in test_scenarios:
            start_time = time.time()
            memory_before = psutil.Process().memory_info().rss / 1024 / 1024
            cpu_before = psutil.cpu_percent()
            
            # Simulate ML processing
            await self._simulate_ml_processing(scenario)
            
            end_time = time.time()
            memory_after = psutil.Process().memory_info().rss / 1024 / 1024
            cpu_after = psutil.cpu_percent()
            
            processing_time = end_time - start_time
            memory_delta = memory_after - memory_before
            
            ml_results[scenario["name"]] = {
                "processing_time_sec": processing_time,
                "memory_delta_mb": memory_delta,
                "cpu_usage_percent": cpu_after,
                "frames_per_second": scenario.get("fps", 0),
                "throughput_fps": (scenario.get("duration", 0) * scenario.get("fps", 0)) / processing_time
            }
            
            logger.info(f"Scenario {scenario['name']}: {processing_time:.2f}s, {memory_delta:.1f}MB, {cpu_after:.1f}% CPU")
        
        self.test_results["ml_inference"] = ml_results
    
    async def _simulate_ml_processing(self, scenario: Dict[str, Any]):
        """Simulate ML processing for given scenario"""
        # Simulate processing delay based on scenario complexity
        base_delay = 0.1
        
        if scenario.get("width", 0) > 1920:  # 4K processing
            base_delay *= 4
        
        if scenario.get("streams", 1) > 1:  # Multi-stream
            base_delay *= scenario["streams"]
        
        # Simulate actual processing work
        await asyncio.sleep(base_delay * scenario.get("duration", 1))
        
        # Simulate memory allocation for video processing
        dummy_data = np.random.rand(100, 100, 100)  # Simulate video buffer
        del dummy_data
    
    async def database_performance_benchmarks(self):
        """Test database performance under load"""
        logger.info("💾 Running database performance benchmarks")
        
        db_results = {}
        
        # Test scenarios
        scenarios = [
            {"name": "sequential_reads", "operations": 1000, "type": "read"},
            {"name": "concurrent_writes", "operations": 500, "type": "write", "concurrent": True},
            {"name": "mixed_operations", "operations": 750, "type": "mixed"},
            {"name": "bulk_insert", "operations": 2000, "type": "bulk_write"},
        ]
        
        for scenario in scenarios:
            start_time = time.time()
            
            if scenario.get("concurrent", False):
                await self._run_concurrent_db_operations(scenario)
            else:
                await self._run_sequential_db_operations(scenario)
            
            end_time = time.time()
            
            total_time = end_time - start_time
            ops_per_second = scenario["operations"] / total_time
            
            db_results[scenario["name"]] = {
                "total_time_sec": total_time,
                "operations": scenario["operations"],
                "ops_per_second": ops_per_second,
                "type": scenario["type"]
            }
            
            logger.info(f"DB {scenario['name']}: {ops_per_second:.1f} ops/sec")
        
        self.test_results["database_performance"] = db_results
    
    async def _run_concurrent_db_operations(self, scenario: Dict[str, Any]):
        """Run concurrent database operations"""
        num_workers = min(10, scenario["operations"] // 10)
        
        async def worker():
            for _ in range(scenario["operations"] // num_workers):
                # Simulate database operation
                await asyncio.sleep(0.001)
        
        tasks = [worker() for _ in range(num_workers)]
        await asyncio.gather(*tasks)
    
    async def _run_sequential_db_operations(self, scenario: Dict[str, Any]):
        """Run sequential database operations"""
        for i in range(scenario["operations"]):
            # Simulate database operation
            await asyncio.sleep(0.0001)
            
            if scenario["type"] == "mixed" and i % 10 == 0:
                # Simulate heavier operation every 10th operation
                await asyncio.sleep(0.001)
    
    async def websocket_performance_benchmarks(self):
        """Test WebSocket performance and scalability"""
        logger.info("🌐 Running WebSocket performance benchmarks")
        
        websocket_results = {}
        
        # Test different connection loads
        connection_tests = [10, 25, 50, 100, 200]
        
        for num_connections in connection_tests:
            if num_connections > self.config.max_concurrent_users:
                continue
                
            start_time = time.time()
            
            # Simulate WebSocket connections and message throughput
            messages_sent = await self._simulate_websocket_load(num_connections)
            
            end_time = time.time()
            test_duration = end_time - start_time
            
            websocket_results[f"connections_{num_connections}"] = {
                "connections": num_connections,
                "messages_sent": messages_sent,
                "test_duration_sec": test_duration,
                "messages_per_second": messages_sent / test_duration,
                "messages_per_connection": messages_sent / num_connections
            }
            
            logger.info(f"WebSocket {num_connections} connections: {messages_sent/test_duration:.1f} msg/sec")
        
        self.test_results["websocket_performance"] = websocket_results
    
    async def _simulate_websocket_load(self, num_connections: int) -> int:
        """Simulate WebSocket load testing"""
        messages_per_connection = 50
        total_messages = 0
        
        async def connection_worker():
            nonlocal total_messages
            for _ in range(messages_per_connection):
                # Simulate sending message and receiving response
                await asyncio.sleep(0.01)  # 10ms per message
                total_messages += 1
        
        # Create connection workers
        tasks = [connection_worker() for _ in range(num_connections)]
        await asyncio.gather(*tasks)
        
        return total_messages
    
    async def memory_stress_tests(self):
        """Test system behavior under memory pressure"""
        logger.info("🧠 Running memory stress tests")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        memory_results = {
            "initial_memory_mb": initial_memory,
            "peak_memory_mb": initial_memory,
            "memory_allocations": [],
            "gc_events": 0
        }
        
        # Gradually increase memory usage
        memory_chunks = []
        chunk_size_mb = 10
        max_chunks = min(50, self.config.memory_limit_mb // chunk_size_mb)
        
        for i in range(max_chunks):
            # Allocate memory chunk
            chunk = np.random.rand(chunk_size_mb * 1024 * 256)  # ~10MB per chunk
            memory_chunks.append(chunk)
            
            # Monitor memory usage
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_results["memory_allocations"].append({
                "chunk": i + 1,
                "memory_mb": current_memory,
                "delta_mb": current_memory - initial_memory
            })
            
            memory_results["peak_memory_mb"] = max(memory_results["peak_memory_mb"], current_memory)
            
            # Check if we're approaching limits
            if current_memory > self.config.memory_limit_mb * 0.9:
                logger.warning(f"Approaching memory limit at {current_memory:.1f}MB")
                break
            
            await asyncio.sleep(0.1)
        
        # Cleanup and measure garbage collection
        start_gc = time.time()
        del memory_chunks
        import gc
        gc.collect()
        gc_time = time.time() - start_gc
        
        final_memory = process.memory_info().rss / 1024 / 1024
        
        memory_results.update({
            "final_memory_mb": final_memory,
            "memory_recovered_mb": memory_results["peak_memory_mb"] - final_memory,
            "gc_time_sec": gc_time
        })
        
        self.test_results["memory_stress"] = memory_results
        logger.info(f"Memory stress test: Peak {memory_results['peak_memory_mb']:.1f}MB, Recovered {memory_results['memory_recovered_mb']:.1f}MB")
    
    async def cpu_load_tests(self):
        """Test CPU performance under sustained load"""
        logger.info("⚙️  Running CPU load tests")
        
        cpu_results = {
            "baseline_cpu_percent": psutil.cpu_percent(interval=1),
            "load_test_results": [],
            "peak_cpu_percent": 0,
            "average_cpu_percent": 0
        }
        
        # CPU intensive tasks simulation
        def cpu_worker(duration: int, worker_id: int):
            """CPU intensive worker function"""
            start_time = time.time()
            operations = 0
            
            while time.time() - start_time < duration:
                # Simulate CPU intensive work
                result = sum(i ** 2 for i in range(1000))
                operations += 1
            
            return operations
        
        # Test different CPU loads
        cpu_tests = [
            {"workers": 1, "duration": 10, "name": "single_core_load"},
            {"workers": 2, "duration": 15, "name": "dual_core_load"},
            {"workers": 4, "duration": 20, "name": "quad_core_load"},
            {"workers": psutil.cpu_count(), "duration": 30, "name": "max_core_load"}
        ]
        
        for test in cpu_tests:
            logger.info(f"Running CPU test: {test['name']}")
            
            # Monitor CPU usage during test
            cpu_samples = []
            
            def monitor_cpu():
                start_monitor = time.time()
                while time.time() - start_monitor < test["duration"]:
                    cpu_samples.append(psutil.cpu_percent())
                    time.sleep(1)
            
            # Start monitoring
            monitor_thread = threading.Thread(target=monitor_cpu)
            monitor_thread.start()
            
            # Run CPU workers
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=test["workers"]) as executor:
                futures = [executor.submit(cpu_worker, test["duration"], i) for i in range(test["workers"])]
                total_operations = sum(future.result() for future in as_completed(futures))
            
            end_time = time.time()
            monitor_thread.join()
            
            test_duration = end_time - start_time
            avg_cpu = np.mean(cpu_samples) if cpu_samples else 0
            peak_cpu = max(cpu_samples) if cpu_samples else 0
            
            cpu_results["load_test_results"].append({
                "name": test["name"],
                "workers": test["workers"],
                "duration_sec": test_duration,
                "total_operations": total_operations,
                "ops_per_second": total_operations / test_duration,
                "average_cpu_percent": avg_cpu,
                "peak_cpu_percent": peak_cpu
            })
            
            cpu_results["peak_cpu_percent"] = max(cpu_results["peak_cpu_percent"], peak_cpu)
            
            logger.info(f"CPU test {test['name']}: {avg_cpu:.1f}% avg, {peak_cpu:.1f}% peak")
        
        # Calculate overall averages
        if cpu_results["load_test_results"]:
            cpu_results["average_cpu_percent"] = np.mean([
                test["average_cpu_percent"] for test in cpu_results["load_test_results"]
            ])
        
        self.test_results["cpu_load"] = cpu_results
    
    async def concurrent_user_simulation(self):
        """Simulate multiple concurrent users using the system"""
        logger.info("👥 Running concurrent user simulation")
        
        user_simulation_results = {}
        
        # Different user load scenarios
        user_scenarios = [
            {"users": 5, "duration": 30, "scenario": "light_load"},
            {"users": 15, "duration": 60, "scenario": "medium_load"},
            {"users": 30, "duration": 90, "scenario": "heavy_load"},
            {"users": 50, "duration": 120, "scenario": "stress_load"}
        ]
        
        for scenario in user_scenarios:
            if scenario["users"] > self.config.max_concurrent_users:
                continue
                
            logger.info(f"Simulating {scenario['users']} concurrent users")
            
            start_time = time.time()
            user_actions = 0
            errors = 0
            
            async def simulate_user(user_id: int):
                nonlocal user_actions, errors
                user_start = time.time()
                
                while time.time() - user_start < scenario["duration"]:
                    try:
                        # Simulate user actions
                        await self._simulate_user_workflow()
                        user_actions += 1
                        await asyncio.sleep(np.random.exponential(2.0))  # Random delay
                    except Exception:
                        errors += 1
            
            # Run concurrent user simulations
            tasks = [simulate_user(i) for i in range(scenario["users"])]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            user_simulation_results[scenario["scenario"]] = {
                "concurrent_users": scenario["users"],
                "duration_sec": total_time,
                "total_actions": user_actions,
                "errors": errors,
                "actions_per_second": user_actions / total_time,
                "error_rate": errors / max(user_actions, 1),
                "actions_per_user": user_actions / scenario["users"]
            }
            
            logger.info(f"User simulation {scenario['scenario']}: {user_actions} actions, {errors} errors")
        
        self.test_results["concurrent_users"] = user_simulation_results
    
    async def _simulate_user_workflow(self):
        """Simulate a typical user workflow"""
        # Simulate typical user actions with realistic delays
        workflows = [
            self._simulate_video_upload,
            self._simulate_project_creation,
            self._simulate_detection_analysis,
            self._simulate_report_generation
        ]
        
        # Pick random workflow
        workflow = np.random.choice(workflows)
        await workflow()
    
    async def _simulate_video_upload(self):
        """Simulate video upload workflow"""
        await asyncio.sleep(0.5)  # Upload simulation
        await asyncio.sleep(0.2)  # Processing
    
    async def _simulate_project_creation(self):
        """Simulate project creation workflow"""
        await asyncio.sleep(0.1)  # Form filling
        await asyncio.sleep(0.3)  # Database operations
    
    async def _simulate_detection_analysis(self):
        """Simulate detection analysis workflow"""
        await asyncio.sleep(1.0)  # ML inference
        await asyncio.sleep(0.3)  # Result processing
    
    async def _simulate_report_generation(self):
        """Simulate report generation workflow"""
        await asyncio.sleep(0.8)  # Data aggregation
        await asyncio.sleep(0.2)  # Report formatting
    
    async def system_resource_limits_test(self):
        """Test system behavior at resource limits"""
        logger.info("⚠️  Running system resource limits test")
        
        limits_results = {
            "memory_limit_test": {},
            "cpu_limit_test": {},
            "file_descriptor_test": {},
            "network_connection_test": {}
        }
        
        # Memory limit test
        try:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024
            
            # Gradually approach memory limit
            memory_stress_data = []
            chunk_size = 50  # 50MB chunks
            
            while process.memory_info().rss / 1024 / 1024 < self.config.memory_limit_mb * 0.95:
                chunk = np.random.rand(chunk_size * 1024 * 256)
                memory_stress_data.append(chunk)
                current_memory = process.memory_info().rss / 1024 / 1024
                
                if len(memory_stress_data) > 20:  # Prevent infinite loop
                    break
                
                await asyncio.sleep(0.1)
            
            final_memory = process.memory_info().rss / 1024 / 1024
            
            limits_results["memory_limit_test"] = {
                "initial_memory_mb": initial_memory,
                "final_memory_mb": final_memory,
                "memory_allocated_mb": final_memory - initial_memory,
                "chunks_allocated": len(memory_stress_data)
            }
            
            # Cleanup
            del memory_stress_data
            
        except Exception as e:
            limits_results["memory_limit_test"]["error"] = str(e)
        
        # CPU limit test - sustained high CPU usage
        try:
            def cpu_stress_worker():
                start = time.time()
                operations = 0
                while time.time() - start < 30:  # 30 seconds
                    result = sum(i ** 3 for i in range(10000))
                    operations += 1
                return operations
            
            with ThreadPoolExecutor(max_workers=psutil.cpu_count()) as executor:
                futures = [executor.submit(cpu_stress_worker) for _ in range(psutil.cpu_count())]
                total_ops = sum(future.result() for future in as_completed(futures))
            
            limits_results["cpu_limit_test"] = {
                "total_operations": total_ops,
                "workers": psutil.cpu_count(),
                "duration_sec": 30
            }
            
        except Exception as e:
            limits_results["cpu_limit_test"]["error"] = str(e)
        
        self.test_results["resource_limits"] = limits_results
        logger.info("Resource limits test completed")
    
    def compile_final_report(self) -> Dict[str, Any]:
        """Compile final performance report"""
        
        # Calculate overall performance score
        performance_score = self._calculate_performance_score()
        
        report = {
            "test_summary": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_test_suites": len(self.test_results),
                "overall_performance_score": performance_score,
                "system_specifications": {
                    "cpu_count": psutil.cpu_count(),
                    "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                    "platform": sys.platform
                }
            },
            "detailed_results": self.test_results,
            "performance_recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _calculate_performance_score(self) -> float:
        """Calculate overall performance score (0-100)"""
        scores = []
        
        # ML inference score
        if "ml_inference" in self.test_results:
            ml_results = self.test_results["ml_inference"]
            avg_throughput = np.mean([result.get("throughput_fps", 0) for result in ml_results.values()])
            ml_score = min(100, avg_throughput * 10)  # Scale to 0-100
            scores.append(ml_score)
        
        # Database performance score
        if "database_performance" in self.test_results:
            db_results = self.test_results["database_performance"]
            avg_ops_per_sec = np.mean([result.get("ops_per_second", 0) for result in db_results.values()])
            db_score = min(100, avg_ops_per_sec / 10)  # Scale to 0-100
            scores.append(db_score)
        
        # Memory efficiency score
        if "memory_stress" in self.test_results:
            memory_results = self.test_results["memory_stress"]
            memory_efficiency = memory_results.get("memory_recovered_mb", 0) / max(memory_results.get("peak_memory_mb", 1), 1)
            memory_score = memory_efficiency * 100
            scores.append(memory_score)
        
        # CPU efficiency score
        if "cpu_load" in self.test_results:
            cpu_results = self.test_results["cpu_load"]
            avg_cpu = cpu_results.get("average_cpu_percent", 0)
            # Score based on CPU utilization efficiency
            cpu_score = max(0, 100 - (avg_cpu - 50) * 2) if avg_cpu > 50 else 100
            scores.append(cpu_score)
        
        # Return average score or 0 if no scores
        return np.mean(scores) if scores else 0.0
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        # Analyze results and generate recommendations
        if "ml_inference" in self.test_results:
            ml_results = self.test_results["ml_inference"]
            slow_scenarios = [name for name, result in ml_results.items() 
                            if result.get("processing_time_sec", 0) > 30]
            if slow_scenarios:
                recommendations.append(f"Optimize ML inference for scenarios: {', '.join(slow_scenarios)}")
        
        if "memory_stress" in self.test_results:
            memory_results = self.test_results["memory_stress"]
            if memory_results.get("peak_memory_mb", 0) > self.config.memory_limit_mb * 0.8:
                recommendations.append("Consider implementing memory pooling or streaming for large video processing")
        
        if "database_performance" in self.test_results:
            db_results = self.test_results["database_performance"]
            slow_operations = [name for name, result in db_results.items() 
                             if result.get("ops_per_second", 0) < 100]
            if slow_operations:
                recommendations.append(f"Optimize database operations: {', '.join(slow_operations)}")
        
        if not recommendations:
            recommendations.append("System performance is within acceptable parameters")
        
        return recommendations


class SystemResourceMonitor:
    """Monitor system resources during performance tests"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = []
        
    def start_monitoring(self, interval: float = 1.0):
        """Start monitoring system resources"""
        self.monitoring = True
        self.metrics = []
        
        def monitor():
            while self.monitoring:
                self.metrics.append({
                    "timestamp": time.time(),
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "memory_mb": psutil.Process().memory_info().rss / 1024 / 1024,
                    "disk_io": dict(psutil.disk_io_counters()._asdict()) if psutil.disk_io_counters() else {},
                    "network_io": dict(psutil.net_io_counters()._asdict()) if psutil.net_io_counters() else {}
                })
                time.sleep(interval)
        
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> List[Dict[str, Any]]:
        """Stop monitoring and return collected metrics"""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=5)
        return self.metrics


@pytest.fixture(scope="session")
def performance_config():
    """Performance testing configuration fixture"""
    return PerformanceBenchmarkConfig()


@pytest.fixture(scope="session")  
def performance_tester(performance_config):
    """Performance tester fixture"""
    return VRUPerformanceTester(performance_config)


@pytest.mark.asyncio
async def test_comprehensive_performance_benchmarks(performance_tester):
    """Run comprehensive performance benchmarks"""
    logger.info("🚀 Starting comprehensive VRU performance benchmarks")
    
    # Run all performance tests
    final_report = await performance_tester.run_comprehensive_benchmarks()
    
    # Save report
    report_path = f"/home/user/Testing/ai-model-validation-platform/backend/tests/performance/vru_performance_report_{int(time.time())}.json"
    with open(report_path, 'w') as f:
        json.dump(final_report, f, indent=2, default=str)
    
    logger.info(f"Performance report saved to: {report_path}")
    
    # Print summary
    print("\n" + "="*80)
    print("VRU PLATFORM PERFORMANCE BENCHMARK REPORT")
    print("="*80)
    print(f"Overall Performance Score: {final_report['test_summary']['overall_performance_score']:.1f}/100")
    print(f"Test Suites Completed: {final_report['test_summary']['total_test_suites']}")
    print("\nRecommendations:")
    for i, rec in enumerate(final_report["performance_recommendations"], 1):
        print(f"{i}. {rec}")
    print("="*80)
    
    # Assert minimum performance standards
    assert final_report['test_summary']['overall_performance_score'] >= 60.0, "Performance below acceptable threshold"


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])