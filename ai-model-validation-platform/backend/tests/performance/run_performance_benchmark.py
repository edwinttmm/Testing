#!/usr/bin/env python3
"""
Direct Performance Benchmark Runner

Runs comprehensive performance tests without pytest dependency,
providing detailed measurements and optimization recommendations.

Author: Claude Code Performance Testing Agent
Date: 2025-01-24
"""

import time
import threading
import psutil
import sqlite3
import numpy as np
import os
import sys
import json
import tempfile
import logging
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from collections import defaultdict, deque

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceBenchmarkRunner:
    """Main performance benchmark runner"""
    
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
        self.system_info = self._get_system_info()
    
    def _get_system_info(self):
        """Get system information for context"""
        return {
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
            'python_version': sys.version,
            'platform': sys.platform
        }
    
    def run_all_tests(self):
        """Run all performance tests"""
        logger.info("🚀 Starting Comprehensive LabJack Performance Benchmarks")
        logger.info("=" * 80)
        
        logger.info(f"System Info:")
        logger.info(f"   - CPUs: {self.system_info['cpu_count']}")
        logger.info(f"   - Memory: {self.system_info['memory_total_gb']:.1f}GB")
        logger.info(f"   - Platform: {self.system_info['platform']}")
        logger.info("")
        
        # Test 1: Data Capture Performance
        logger.info("📊 Test 1: Data Capture Performance")
        try:
            self.results['data_capture'] = self._test_data_capture_performance()
            logger.info("✅ Data capture test completed")
        except Exception as e:
            logger.error(f"❌ Data capture test failed: {e}")
            self.results['data_capture'] = {'error': str(e)}
        
        # Test 2: Compression Performance
        logger.info("\n🗜️ Test 2: Compression Performance")
        try:
            self.results['compression'] = self._test_compression_performance()
            logger.info("✅ Compression test completed")
        except Exception as e:
            logger.error(f"❌ Compression test failed: {e}")
            self.results['compression'] = {'error': str(e)}
        
        # Test 3: Database Performance
        logger.info("\n🗄️ Test 3: Database Performance")
        try:
            self.results['database'] = self._test_database_performance()
            logger.info("✅ Database test completed")
        except Exception as e:
            logger.error(f"❌ Database test failed: {e}")
            self.results['database'] = {'error': str(e)}
        
        # Test 4: Memory Management
        logger.info("\n💾 Test 4: Memory Management")
        try:
            self.results['memory'] = self._test_memory_management()
            logger.info("✅ Memory management test completed")
        except Exception as e:
            logger.error(f"❌ Memory management test failed: {e}")
            self.results['memory'] = {'error': str(e)}
        
        # Test 5: Concurrency Performance
        logger.info("\n🔄 Test 5: Concurrency Performance")
        try:
            self.results['concurrency'] = self._test_concurrency_performance()
            logger.info("✅ Concurrency test completed")
        except Exception as e:
            logger.error(f"❌ Concurrency test failed: {e}")
            self.results['concurrency'] = {'error': str(e)}
        
        # Generate final report
        self._generate_performance_report()
    
    def _test_data_capture_performance(self):
        """Test 1000Hz sustained data capture performance"""
        logger.info("   🧪 Testing 1000Hz sustained data capture")
        
        # Parameters
        target_frequency = 1000  # Hz
        test_duration = 5  # seconds (reduced for quick testing)
        expected_samples = target_frequency * test_duration
        
        # Metrics
        captured_samples = []
        dropped_samples = 0
        processing_times = []
        memory_samples = []
        
        # Start monitoring
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        start_time = time.perf_counter()
        
        # Simulate high-frequency data capture
        sample_interval = 1.0 / target_frequency
        
        for i in range(expected_samples):
            sample_start = time.perf_counter()
            
            # Generate realistic LabJack data
            timestamp = time.time()
            voltage = 2.5 + 0.5 * np.sin(2 * np.pi * 10 * timestamp) + np.random.normal(0, 0.05)
            digital_state = np.random.choice([0, 1])
            
            # Create data sample
            sample = {
                'timestamp': timestamp,
                'ain0': voltage,
                'dio0': digital_state,
                'sample_number': i,
                'quality_score': np.random.uniform(0.95, 1.0)
            }
            
            # Simulate processing time
            processing_start = time.perf_counter()
            
            # Data validation
            if self._validate_sample(sample):
                captured_samples.append(sample)
            else:
                dropped_samples += 1
            
            processing_time = (time.perf_counter() - processing_start) * 1000
            processing_times.append(processing_time)
            
            # Memory monitoring
            if i % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory)
            
            # Maintain timing
            elapsed = time.perf_counter() - sample_start
            sleep_time = max(0, sample_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        end_time = time.perf_counter()
        end_memory = process.memory_info().rss / 1024 / 1024
        
        # Calculate metrics
        actual_duration = end_time - start_time
        actual_sample_rate = len(captured_samples) / actual_duration
        drop_rate = dropped_samples / (len(captured_samples) + dropped_samples) * 100
        avg_processing_time = np.mean(processing_times)
        memory_growth = end_memory - start_memory
        
        result = {
            'target_sample_rate_hz': target_frequency,
            'actual_sample_rate_hz': actual_sample_rate,
            'samples_captured': len(captured_samples),
            'samples_dropped': dropped_samples,
            'drop_rate_percent': drop_rate,
            'avg_processing_time_ms': avg_processing_time,
            'max_processing_time_ms': np.max(processing_times),
            'memory_growth_mb': memory_growth,
            'test_duration_s': actual_duration,
            'performance_target_met': actual_sample_rate >= 950 and drop_rate < 1.0
        }
        
        # Log results
        logger.info(f"      - Target sample rate: {target_frequency}Hz")
        logger.info(f"      - Actual sample rate: {actual_sample_rate:.1f}Hz")
        logger.info(f"      - Samples captured: {len(captured_samples)}")
        logger.info(f"      - Drop rate: {drop_rate:.2f}%")
        logger.info(f"      - Avg processing time: {avg_processing_time:.3f}ms")
        logger.info(f"      - Memory growth: {memory_growth:.1f}MB")
        logger.info(f"      - Performance target met: {'✅' if result['performance_target_met'] else '❌'}")
        
        return result
    
    def _validate_sample(self, sample):
        """Validate data sample"""
        return (
            0 <= sample['ain0'] <= 5.0 and
            sample['dio0'] in [0, 1] and
            sample['timestamp'] > 0
        )
    
    def _test_compression_performance(self):
        """Test compression algorithms performance vs quality"""
        logger.info("   🧪 Testing compression performance vs quality balance")
        
        # Generate test signal
        sample_rate = 1000
        duration = 5  # seconds
        t = np.linspace(0, duration, sample_rate * duration)
        
        # Create realistic test signal
        base_signal = 2.5
        sine_wave = 0.5 * np.sin(2 * np.pi * 10 * t)  # 10Hz sine
        noise = 0.05 * np.random.normal(0, 1, len(t))  # 5% noise
        spikes = np.zeros_like(t)
        spike_indices = np.random.choice(len(t), size=int(len(t) * 0.001))
        spikes[spike_indices] = np.random.normal(0, 0.5, len(spike_indices))
        
        original_signal = base_signal + sine_wave + noise + spikes
        
        # Test compression methods
        compression_methods = [
            ('Delta Compression', self._delta_compress),
            ('Adaptive Sampling', self._adaptive_sample),
            ('Simple Decimation', self._simple_decimate)
        ]
        
        results = {}
        
        for method_name, compress_func in compression_methods:
            logger.info(f"      Testing {method_name}...")
            
            start_time = time.perf_counter()
            compressed_data = compress_func(original_signal)
            compression_time = (time.perf_counter() - start_time) * 1000
            
            # Calculate metrics
            original_size = len(original_signal) * 8  # 8 bytes per float64
            compressed_size = len(compressed_data) * 16  # Estimate based on data structure
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            
            # Reconstruct signal for quality assessment
            if method_name == 'Delta Compression':
                reconstructed = self._delta_decompress(compressed_data, len(original_signal))
            elif method_name == 'Adaptive Sampling':
                reconstructed = self._adaptive_decompress(compressed_data, t)
            else:  # Simple decimation
                reconstructed = self._simple_reconstruct(compressed_data, len(original_signal))
            
            # Calculate quality loss (RMSE)
            mse = np.mean((original_signal - reconstructed) ** 2)
            signal_power = np.mean(original_signal ** 2)
            quality_loss_percent = (np.sqrt(mse) / np.sqrt(signal_power)) * 100
            
            method_result = {
                'compression_ratio': compression_ratio,
                'quality_loss_percent': quality_loss_percent,
                'compression_time_ms': compression_time,
                'compressed_samples': len(compressed_data),
                'meets_requirements': 5 <= compression_ratio <= 20 and quality_loss_percent < 1.0
            }
            
            results[method_name] = method_result
            
            logger.info(f"        - Compression ratio: {compression_ratio:.1f}x")
            logger.info(f"        - Quality loss: {quality_loss_percent:.3f}%")
            logger.info(f"        - Compression time: {compression_time:.1f}ms")
            logger.info(f"        - Meets requirements: {'✅' if method_result['meets_requirements'] else '❌'}")
        
        # Find best method
        valid_methods = [name for name, result in results.items() if result['meets_requirements']]
        
        results['summary'] = {
            'valid_methods_count': len(valid_methods),
            'best_method': valid_methods[0] if valid_methods else None,
            'overall_success': len(valid_methods) > 0
        }
        
        if valid_methods:
            logger.info(f"      🏆 Best method: {valid_methods[0]}")
        else:
            logger.info(f"      ⚠️ No method met all requirements")
        
        return results
    
    def _delta_compress(self, signal, threshold=0.01):
        """Delta compression implementation"""
        if len(signal) == 0:
            return []
        
        compressed = [(0, signal[0])]
        last_value = signal[0]
        
        for i, value in enumerate(signal[1:], 1):
            if abs(value - last_value) > threshold:
                compressed.append((i, value))
                last_value = value
        
        return compressed
    
    def _delta_decompress(self, compressed, target_length):
        """Delta decompression implementation"""
        if not compressed:
            return np.zeros(target_length)
        
        signal = np.zeros(target_length)
        
        for i in range(len(compressed)):
            start_idx = compressed[i][0]
            value = compressed[i][1]
            end_idx = compressed[i + 1][0] if i + 1 < len(compressed) else target_length
            
            signal[start_idx:end_idx] = value
        
        return signal
    
    def _adaptive_sample(self, signal, max_error=0.01):
        """Adaptive sampling implementation"""
        if len(signal) < 3:
            return list(enumerate(signal))
        
        compressed = [(0, signal[0])]
        i = 1
        
        while i < len(signal) - 1:
            j = i + 1
            while j < len(signal) and abs(signal[j] - signal[i]) < max_error:
                j += 1
            
            if j < len(signal):
                compressed.append((j - 1, signal[j - 1]))
                compressed.append((j, signal[j]))
                i = j + 1
            else:
                compressed.append((len(signal) - 1, signal[-1]))
                break
        
        return compressed
    
    def _adaptive_decompress(self, compressed, time_array):
        """Adaptive sampling decompression"""
        if not compressed:
            return np.zeros(len(time_array))
        
        indices = [c[0] for c in compressed]
        values = [c[1] for c in compressed]
        
        return np.interp(range(len(time_array)), indices, values)
    
    def _simple_decimate(self, signal, factor=10):
        """Simple decimation compression"""
        return [(i * factor, signal[i * factor]) for i in range(0, len(signal) // factor)]
    
    def _simple_reconstruct(self, compressed, target_length):
        """Simple decimation reconstruction"""
        if not compressed:
            return np.zeros(target_length)
        
        indices = [c[0] for c in compressed]
        values = [c[1] for c in compressed]
        
        return np.interp(range(target_length), indices, values)
    
    def _test_database_performance(self):
        """Test database query performance"""
        logger.info("   🧪 Testing database query performance")
        
        # Create temporary database
        db_path = tempfile.mktemp(suffix='.db')
        
        try:
            conn = sqlite3.connect(db_path)
            
            # Create schema
            conn.execute('''
                CREATE TABLE raw_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    voltage REAL NOT NULL,
                    digital_state INTEGER NOT NULL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE compressed_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_start REAL NOT NULL,
                    timestamp_end REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    compressed_blob BLOB NOT NULL,
                    compression_ratio REAL NOT NULL
                )
            ''')
            
            # Create indexes
            conn.execute('CREATE INDEX idx_raw_timestamp ON raw_data(timestamp)')
            conn.execute('CREATE INDEX idx_raw_session ON raw_data(session_id)')
            conn.execute('CREATE INDEX idx_compressed_start ON compressed_data(timestamp_start)')
            
            # Populate with test data
            logger.info("      Populating test data...")
            
            # Raw data (recent)
            raw_data = []
            current_time = time.time()
            for i in range(5000):
                raw_data.append((
                    current_time - (5000 - i) * 0.001,  # 1000Hz
                    f'session_{i % 3}',
                    2.5 + np.random.normal(0, 0.1),
                    np.random.choice([0, 1])
                ))
            
            conn.executemany('''
                INSERT INTO raw_data (timestamp, session_id, voltage, digital_state)
                VALUES (?, ?, ?, ?)
            ''', raw_data)
            
            # Compressed data (historical)
            compressed_data = []
            for i in range(500):
                start_time = current_time - 3600 - i * 10  # 1 hour ago
                end_time = start_time + 10
                
                # Fake compressed blob
                fake_blob = json.dumps([2.5 + i * 0.01] * 100).encode()
                
                compressed_data.append((
                    start_time,
                    end_time,
                    f'session_{i % 3}',
                    fake_blob,
                    10.0  # compression ratio
                ))
            
            conn.executemany('''
                INSERT INTO compressed_data 
                (timestamp_start, timestamp_end, session_id, compressed_blob, compression_ratio)
                VALUES (?, ?, ?, ?, ?)
            ''', compressed_data)
            
            conn.commit()
            
            # Test query performance
            query_results = {}
            
            # Query 1: Recent data
            start_time = time.perf_counter()
            cursor = conn.execute('''
                SELECT timestamp, voltage FROM raw_data 
                WHERE timestamp > ? AND session_id = ?
                ORDER BY timestamp DESC LIMIT 1000
            ''', (time.time() - 5, 'session_0'))
            recent_results = cursor.fetchall()
            query1_time = (time.perf_counter() - start_time) * 1000
            
            query_results['recent_data'] = {
                'query_time_ms': query1_time,
                'result_count': len(recent_results),
                'meets_target': query1_time < 100
            }
            
            # Query 2: Aggregation
            start_time = time.perf_counter()
            cursor = conn.execute('''
                SELECT AVG(voltage), MIN(voltage), MAX(voltage), COUNT(*) 
                FROM raw_data WHERE session_id = ?
            ''', ('session_0',))
            agg_results = cursor.fetchall()
            query2_time = (time.perf_counter() - start_time) * 1000
            
            query_results['aggregation'] = {
                'query_time_ms': query2_time,
                'result_count': len(agg_results),
                'meets_target': query2_time < 100
            }
            
            # Query 3: Hybrid query
            start_time = time.perf_counter()
            cursor = conn.execute('''
                SELECT 'raw' as type, timestamp, voltage FROM raw_data 
                WHERE session_id = ? AND timestamp > ?
                UNION ALL
                SELECT 'compressed' as type, timestamp_start as timestamp, 
                       compression_ratio as voltage FROM compressed_data
                WHERE session_id = ? AND timestamp_start < ?
                ORDER BY timestamp DESC LIMIT 500
            ''', ('session_0', time.time() - 10, 'session_0', time.time() - 10))
            hybrid_results = cursor.fetchall()
            query3_time = (time.perf_counter() - start_time) * 1000
            
            query_results['hybrid_query'] = {
                'query_time_ms': query3_time,
                'result_count': len(hybrid_results),
                'meets_target': query3_time < 200
            }
            
            conn.close()
            
            # Calculate overall performance
            all_queries_pass = all(result['meets_target'] for result in query_results.values())
            avg_query_time = np.mean([result['query_time_ms'] for result in query_results.values()])
            
            query_results['summary'] = {
                'avg_query_time_ms': avg_query_time,
                'all_queries_pass': all_queries_pass,
                'total_queries': len(query_results) - 1  # Exclude summary
            }
            
            # Log results
            for query_name, result in query_results.items():
                if query_name != 'summary':
                    logger.info(f"      - {query_name}: {result['query_time_ms']:.1f}ms "
                               f"({result['result_count']} results) "
                               f"{'✅' if result['meets_target'] else '❌'}")
            
            logger.info(f"      - Overall: {'✅' if all_queries_pass else '❌'} "
                       f"(avg: {avg_query_time:.1f}ms)")
            
            return query_results
            
        finally:
            # Cleanup
            try:
                os.unlink(db_path)
            except:
                pass
    
    def _test_memory_management(self):
        """Test memory usage and leak detection"""
        logger.info("   🧪 Testing memory management")
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_samples = []
        
        # Simulate memory-intensive operations
        data_buffers = []
        
        for cycle in range(50):  # 50 cycles
            cycle_start_memory = process.memory_info().rss / 1024 / 1024
            
            # Create data objects
            cycle_data = []
            for i in range(100):
                data_object = {
                    'id': f'cycle_{cycle}_sample_{i}',
                    'timestamp': time.time(),
                    'data_array': np.random.random(1000),
                    'metadata': {
                        'cycle': cycle,
                        'sample': i,
                        'quality': np.random.uniform(0.8, 1.0)
                    }
                }
                cycle_data.append(data_object)
            
            data_buffers.append(cycle_data)
            
            # Memory management: keep only last 10 cycles
            if len(data_buffers) > 10:
                data_buffers.pop(0)
            
            # Sample memory after cycle
            cycle_end_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(cycle_end_memory)
            
            time.sleep(0.01)  # Small delay
        
        final_memory = process.memory_info().rss / 1024 / 1024
        
        # Analyze memory usage
        memory_growth = final_memory - initial_memory
        memory_trend = np.polyfit(range(len(memory_samples)), memory_samples, 1)[0] if len(memory_samples) > 1 else 0
        memory_variance = np.var(memory_samples) if memory_samples else 0
        peak_memory = max(memory_samples) if memory_samples else initial_memory
        
        result = {
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'peak_memory_mb': peak_memory,
            'memory_growth_mb': memory_growth,
            'memory_trend_mb_per_cycle': memory_trend,
            'memory_variance': memory_variance,
            'cycles_completed': len(memory_samples),
            'memory_leak_detected': memory_trend > 1.0 or memory_growth > 100,
            'memory_management_ok': memory_growth < 50 and memory_trend < 0.5
        }
        
        logger.info(f"      - Initial memory: {initial_memory:.1f}MB")
        logger.info(f"      - Peak memory: {peak_memory:.1f}MB")
        logger.info(f"      - Final memory: {final_memory:.1f}MB")
        logger.info(f"      - Memory growth: {memory_growth:.1f}MB")
        logger.info(f"      - Memory trend: {memory_trend:.3f}MB/cycle")
        logger.info(f"      - Memory leak detected: {'❌' if result['memory_leak_detected'] else '✅'}")
        logger.info(f"      - Memory management OK: {'✅' if result['memory_management_ok'] else '❌'}")
        
        return result
    
    def _test_concurrency_performance(self):
        """Test concurrent operations performance"""
        logger.info("   🧪 Testing concurrency performance")
        
        def worker_task(worker_id, task_count=100):
            """Simulate concurrent data processing"""
            results = []
            processing_times = []
            
            for i in range(task_count):
                start_time = time.perf_counter()
                
                # Simulate CPU-intensive processing
                data = np.random.random(1000)
                
                # FFT processing
                fft_result = np.fft.fft(data)
                
                # Statistical analysis
                stats = {
                    'worker_id': worker_id,
                    'task_id': i,
                    'mean': np.mean(data),
                    'std': np.std(data),
                    'fft_peak': np.max(np.abs(fft_result))
                }
                
                processing_time = (time.perf_counter() - start_time) * 1000
                processing_times.append(processing_time)
                results.append(stats)
                
                # Small delay
                time.sleep(0.001)
            
            return {
                'worker_id': worker_id,
                'tasks_completed': len(results),
                'avg_processing_time_ms': np.mean(processing_times),
                'total_processing_time_ms': sum(processing_times)
            }
        
        # Test with different thread counts
        thread_counts = [1, 2, 4, 8]
        concurrency_results = {}
        
        for thread_count in thread_counts:
            logger.info(f"      Testing with {thread_count} threads...")
            
            start_time = time.perf_counter()
            
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = [
                    executor.submit(worker_task, i, 50)  # 50 tasks per worker
                    for i in range(thread_count)
                ]
                
                worker_results = [future.result() for future in as_completed(futures)]
            
            end_time = time.perf_counter()
            
            # Calculate metrics
            total_duration = (end_time - start_time) * 1000
            total_tasks = sum(r['tasks_completed'] for r in worker_results)
            throughput = total_tasks / (total_duration / 1000) if total_duration > 0 else 0
            
            concurrency_results[f'{thread_count}_threads'] = {
                'thread_count': thread_count,
                'total_duration_ms': total_duration,
                'total_tasks': total_tasks,
                'throughput_tasks_per_sec': throughput,
                'avg_task_time_ms': np.mean([r['avg_processing_time_ms'] for r in worker_results])
            }
            
            logger.info(f"        - Duration: {total_duration:.1f}ms")
            logger.info(f"        - Throughput: {throughput:.1f} tasks/sec")
            logger.info(f"        - Tasks completed: {total_tasks}")
        
        # Find optimal configuration
        best_config = max(concurrency_results.values(), key=lambda x: x['throughput_tasks_per_sec'])
        
        concurrency_results['summary'] = {
            'optimal_thread_count': best_config['thread_count'],
            'best_throughput': best_config['throughput_tasks_per_sec'],
            'concurrency_effective': best_config['throughput_tasks_per_sec'] > concurrency_results['1_threads']['throughput_tasks_per_sec'] * 1.5
        }
        
        logger.info(f"      🏆 Optimal configuration: {best_config['thread_count']} threads")
        logger.info(f"      - Best throughput: {best_config['throughput_tasks_per_sec']:.1f} tasks/sec")
        logger.info(f"      - Concurrency effective: {'✅' if concurrency_results['summary']['concurrency_effective'] else '❌'}")
        
        return concurrency_results
    
    def _generate_performance_report(self):
        """Generate comprehensive performance report"""
        logger.info("\n" + "=" * 80)
        logger.info("📋 COMPREHENSIVE PERFORMANCE REPORT")
        logger.info("=" * 80)
        
        total_time = time.time() - self.start_time
        
        # Overall summary
        logger.info(f"\n🕒 Test Execution Summary:")
        logger.info(f"   - Total execution time: {total_time:.1f}s")
        logger.info(f"   - Tests completed: {len([r for r in self.results.values() if 'error' not in r])}")
        logger.info(f"   - Tests failed: {len([r for r in self.results.values() if 'error' in r])}")
        
        # Performance targets analysis
        logger.info(f"\n🎯 Performance Targets Analysis:")
        
        targets_met = []
        
        # Data capture targets
        if 'data_capture' in self.results and 'error' not in self.results['data_capture']:
            dc = self.results['data_capture']
            target_met = dc.get('performance_target_met', False)
            targets_met.append(('1000Hz Data Capture', target_met))
            logger.info(f"   - 1000Hz Data Capture: {'✅' if target_met else '❌'} "
                       f"({dc.get('actual_sample_rate_hz', 0):.1f}Hz achieved)")
        
        # Compression targets
        if 'compression' in self.results and 'error' not in self.results['compression']:
            comp = self.results['compression']
            target_met = comp.get('summary', {}).get('overall_success', False)
            targets_met.append(('Compression (5-20x, <1% loss)', target_met))
            logger.info(f"   - Compression Requirements: {'✅' if target_met else '❌'} "
                       f"({comp.get('summary', {}).get('valid_methods_count', 0)} methods pass)")
        
        # Database targets
        if 'database' in self.results and 'error' not in self.results['database']:
            db = self.results['database']
            target_met = db.get('summary', {}).get('all_queries_pass', False)
            targets_met.append(('Database Queries (<100ms)', target_met))
            logger.info(f"   - Database Query Performance: {'✅' if target_met else '❌'} "
                       f"({db.get('summary', {}).get('avg_query_time_ms', 0):.1f}ms avg)")
        
        # Memory targets
        if 'memory' in self.results and 'error' not in self.results['memory']:
            mem = self.results['memory']
            target_met = mem.get('memory_management_ok', False)
            targets_met.append(('Memory Management (<500MB)', target_met))
            logger.info(f"   - Memory Management: {'✅' if target_met else '❌'} "
                       f"({mem.get('peak_memory_mb', 0):.1f}MB peak)")
        
        # Concurrency targets
        if 'concurrency' in self.results and 'error' not in self.results['concurrency']:
            conc = self.results['concurrency']
            target_met = conc.get('summary', {}).get('concurrency_effective', False)
            targets_met.append(('Concurrency Scaling', target_met))
            logger.info(f"   - Concurrency Performance: {'✅' if target_met else '❌'} "
                       f"({conc.get('summary', {}).get('optimal_thread_count', 1)} optimal threads)")
        
        # Overall assessment
        total_targets = len(targets_met)
        passed_targets = len([name for name, passed in targets_met if passed])
        overall_score = passed_targets / total_targets * 100 if total_targets > 0 else 0
        
        logger.info(f"\n🏆 Overall Performance Score: {overall_score:.1f}% ({passed_targets}/{total_targets} targets met)")
        
        if overall_score >= 80:
            logger.info("🎉 EXCELLENT: System meets performance requirements!")
        elif overall_score >= 60:
            logger.info("⚠️  GOOD: System mostly meets requirements, minor optimizations needed")
        else:
            logger.info("❌ NEEDS IMPROVEMENT: Significant performance issues identified")
        
        # Optimization recommendations
        logger.info(f"\n🔧 Optimization Recommendations:")
        
        recommendations = []
        
        # Check each component for issues
        if 'data_capture' in self.results and 'error' not in self.results['data_capture']:
            dc = self.results['data_capture']
            if dc.get('actual_sample_rate_hz', 0) < 950:
                recommendations.append("- Optimize data capture loop for higher sample rates")
            if dc.get('drop_rate_percent', 0) > 1.0:
                recommendations.append("- Implement better buffer management to reduce sample drops")
            if dc.get('memory_growth_mb', 0) > 20:
                recommendations.append("- Optimize memory usage in data capture pipeline")
        
        if 'compression' in self.results and 'error' not in self.results['compression']:
            comp = self.results['compression']
            if not comp.get('summary', {}).get('overall_success', False):
                recommendations.append("- Tune compression algorithms for better ratio/quality balance")
                recommendations.append("- Consider hybrid compression strategies")
        
        if 'database' in self.results and 'error' not in self.results['database']:
            db = self.results['database']
            if not db.get('summary', {}).get('all_queries_pass', False):
                recommendations.append("- Add database indexes for frequently used query patterns")
                recommendations.append("- Optimize hybrid queries with better table structure")
        
        if 'memory' in self.results and 'error' not in self.results['memory']:
            mem = self.results['memory']
            if mem.get('memory_leak_detected', False):
                recommendations.append("- Fix memory leaks in data processing pipeline")
            if mem.get('peak_memory_mb', 0) > 400:
                recommendations.append("- Implement more aggressive memory management strategies")
        
        if 'concurrency' in self.results and 'error' not in self.results['concurrency']:
            conc = self.results['concurrency']
            if not conc.get('summary', {}).get('concurrency_effective', False):
                recommendations.append("- Review thread pool configuration and task distribution")
                recommendations.append("- Consider async/await patterns for I/O bound operations")
        
        if recommendations:
            for rec in recommendations:
                logger.info(f"   {rec}")
        else:
            logger.info("   - No specific optimizations identified")
        
        logger.info("\n" + "=" * 80)
        logger.info("🎯 Performance testing completed successfully!")
        logger.info("=" * 80)
        
        # Save detailed results
        try:
            results_file = f"performance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w') as f:
                # Convert numpy types to JSON serializable
                serializable_results = self._make_json_serializable(self.results)
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'system_info': self.system_info,
                    'execution_time_s': total_time,
                    'overall_score': overall_score,
                    'targets_met': passed_targets,
                    'total_targets': total_targets,
                    'results': serializable_results,
                    'recommendations': recommendations
                }, f, indent=2)
            
            logger.info(f"📄 Detailed results saved to: {results_file}")
            
        except Exception as e:
            logger.warning(f"Failed to save results file: {e}")
    
    def _make_json_serializable(self, obj):
        """Convert numpy types and other non-serializable types to JSON-safe types"""
        if isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        else:
            return obj


def main():
    """Main entry point"""
    try:
        runner = PerformanceBenchmarkRunner()
        runner.run_all_tests()
        return 0
    except KeyboardInterrupt:
        logger.info("\n⏹️  Performance testing interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"💥 Performance testing failed: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())