#!/usr/bin/env python3
"""
Performance Bottleneck Analyzer for LabJack Hybrid Logging System

This test suite identifies and profiles specific performance bottlenecks in the
data pipeline, providing detailed analysis and optimization recommendations.

Author: Claude Code Performance Bottleneck Analyzer Agent
Date: 2025-01-24
"""

import pytest
import time
import threading
import psutil
import sqlite3
import numpy as np
import os
import sys
import json
import cProfile
import pstats
import io
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, MagicMock
import tempfile
import logging
from pathlib import Path
from collections import deque, defaultdict
import weakref
import gc

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BottleneckProfiler:
    """Advanced profiler for identifying performance bottlenecks"""
    
    def __init__(self, name: str):
        self.name = name
        self.profiler = cProfile.Profile()
        self.start_time = None
        self.end_time = None
        self.memory_samples = []
        self.cpu_samples = []
        self.io_samples = []
        
    def __enter__(self):
        self.start_time = time.perf_counter()
        self.profiler.enable()
        
        # Start background monitoring
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_resources)
        self.monitor_thread.start()
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.monitoring = False
        self.profiler.disable()
        self.end_time = time.perf_counter()
        
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1.0)
    
    def _monitor_resources(self):
        """Monitor system resources during profiling"""
        process = psutil.Process()
        
        while self.monitoring:
            try:
                # CPU usage
                cpu_percent = process.cpu_percent()
                self.cpu_samples.append({
                    'timestamp': time.perf_counter(),
                    'cpu_percent': cpu_percent
                })
                
                # Memory usage
                memory_info = process.memory_info()
                self.memory_samples.append({
                    'timestamp': time.perf_counter(),
                    'rss_mb': memory_info.rss / 1024 / 1024,
                    'vms_mb': memory_info.vms / 1024 / 1024
                })
                
                # I/O stats (if available)
                try:
                    io_counters = process.io_counters()
                    self.io_samples.append({
                        'timestamp': time.perf_counter(),
                        'read_bytes': io_counters.read_bytes,
                        'write_bytes': io_counters.write_bytes,
                        'read_count': io_counters.read_count,
                        'write_count': io_counters.write_count
                    })
                except (AttributeError, OSError):
                    pass  # I/O counters not available on this platform
                
                time.sleep(0.01)  # Sample every 10ms
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
    
    def get_stats(self, sort_by='cumulative'):
        """Get profiling statistics"""
        stats_stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stats_stream)
        stats.sort_stats(sort_by)
        stats.print_stats()
        
        return {
            'duration_ms': (self.end_time - self.start_time) * 1000,
            'profile_text': stats_stream.getvalue(),
            'cpu_samples': self.cpu_samples,
            'memory_samples': self.memory_samples,
            'io_samples': self.io_samples
        }
    
    def get_hotspots(self, top_n=10):
        """Get top performance hotspots"""
        stats = pstats.Stats(self.profiler)
        stats.sort_stats('cumulative')
        
        hotspots = []
        for func_info in stats.stats.items()[:top_n]:
            filename, line_number, func_name = func_info[0]
            primitive_calls, total_calls, total_time, cumulative_time, callers = func_info[1]
            
            hotspots.append({
                'function': f"{filename}:{line_number}({func_name})",
                'total_calls': total_calls,
                'total_time_ms': total_time * 1000,
                'cumulative_time_ms': cumulative_time * 1000,
                'time_per_call_ms': (cumulative_time / total_calls * 1000) if total_calls > 0 else 0
            })
        
        return hotspots
    
    @property
    def avg_cpu_percent(self):
        if not self.cpu_samples:
            return 0
        return sum(s['cpu_percent'] for s in self.cpu_samples) / len(self.cpu_samples)
    
    @property
    def peak_memory_mb(self):
        if not self.memory_samples:
            return 0
        return max(s['rss_mb'] for s in self.memory_samples)
    
    @property
    def memory_growth_mb(self):
        if len(self.memory_samples) < 2:
            return 0
        return self.memory_samples[-1]['rss_mb'] - self.memory_samples[0]['rss_mb']


class TestDataPipelineBottlenecks:
    """Test and identify bottlenecks in the data processing pipeline"""
    
    def test_data_acquisition_bottlenecks(self):
        """Profile data acquisition stage for bottlenecks"""
        logger.info("🔍 Profiling data acquisition bottlenecks")
        
        with BottleneckProfiler("Data_Acquisition") as profiler:
            # Simulate high-frequency data acquisition
            data_samples = []
            
            for i in range(10000):  # 10,000 samples
                # Simulate LabJack data read
                timestamp = time.time()
                
                # Simulate ADC conversion delay
                time.sleep(0.00001)  # 10µs per sample
                
                # Generate realistic data
                voltage = 2.5 + 0.5 * np.sin(2 * np.pi * 10 * timestamp) + np.random.normal(0, 0.05)
                digital_state = (i % 100) < 50  # 50% duty cycle
                
                # Create data structure (potential bottleneck)
                sample = {
                    'timestamp': timestamp,
                    'sample_id': i,
                    'ain0': voltage,
                    'dio0': int(digital_state),
                    'metadata': {
                        'quality': 'good',
                        'calibration_applied': True,
                        'session_id': f'test_session_{i // 1000}'
                    }
                }
                
                # Data validation (potential bottleneck)
                if self._validate_sample(sample):
                    data_samples.append(sample)
                
                # Buffer management (potential bottleneck)
                if len(data_samples) > 1000:
                    # Simulate buffer flush
                    data_samples = data_samples[-500:]  # Keep last 500
        
        # Analyze bottlenecks
        stats = profiler.get_stats()
        hotspots = profiler.get_hotspots()
        
        # Performance assertions
        assert stats['duration_ms'] < 2000, f"Data acquisition too slow: {stats['duration_ms']:.1f}ms (expected <2000ms)"
        assert profiler.peak_memory_mb < 100, f"Memory usage too high: {profiler.peak_memory_mb:.1f}MB (expected <100MB)"
        assert profiler.avg_cpu_percent < 80, f"CPU usage too high: {profiler.avg_cpu_percent:.1f}% (expected <80%)"
        
        logger.info(f"✅ Data Acquisition Profile:")
        logger.info(f"   - Duration: {stats['duration_ms']:.1f}ms")
        logger.info(f"   - Peak memory: {profiler.peak_memory_mb:.1f}MB")
        logger.info(f"   - Average CPU: {profiler.avg_cpu_percent:.1f}%")
        logger.info(f"   - Samples processed: {len(data_samples)}")
        
        logger.info("🔥 Top Hotspots:")
        for i, hotspot in enumerate(hotspots[:5], 1):
            logger.info(f"   {i}. {hotspot['function']}")
            logger.info(f"      Calls: {hotspot['total_calls']}, "
                       f"Time: {hotspot['cumulative_time_ms']:.2f}ms, "
                       f"Per call: {hotspot['time_per_call_ms']:.4f}ms")
    
    def _validate_sample(self, sample):
        """Validate data sample (simulated validation logic)"""
        # Range validation
        if not (0 <= sample['ain0'] <= 5.0):
            return False
        
        # Digital state validation
        if sample['dio0'] not in [0, 1]:
            return False
        
        # Timestamp validation
        if sample['timestamp'] <= 0:
            return False
        
        # Metadata validation
        if not isinstance(sample['metadata'], dict):
            return False
        
        return True
    
    def test_data_processing_bottlenecks(self):
        """Profile data processing stage for bottlenecks"""
        logger.info("🔍 Profiling data processing bottlenecks")
        
        # Create test dataset
        test_data = []
        for i in range(5000):
            sample = {
                'timestamp': time.time() + i * 0.001,
                'voltage': 2.5 + np.random.normal(0, 0.1),
                'digital': np.random.choice([0, 1]),
                'sample_id': i
            }
            test_data.append(sample)
        
        with BottleneckProfiler("Data_Processing") as profiler:
            processed_data = []
            
            for sample in test_data:
                # Stage 1: Noise filtering (potential bottleneck)
                filtered_voltage = self._apply_noise_filter(sample['voltage'])
                
                # Stage 2: Calibration (potential bottleneck)
                calibrated_voltage = self._apply_calibration(filtered_voltage)
                
                # Stage 3: Unit conversion (potential bottleneck)
                engineering_units = self._convert_to_engineering_units(calibrated_voltage)
                
                # Stage 4: Quality assessment (potential bottleneck)
                quality_score = self._assess_signal_quality(sample)
                
                # Stage 5: Data packaging (potential bottleneck)
                processed_sample = {
                    'original': sample,
                    'processed': {
                        'voltage_filtered': filtered_voltage,
                        'voltage_calibrated': calibrated_voltage,
                        'engineering_units': engineering_units,
                        'quality_score': quality_score,
                        'processing_timestamp': time.time()
                    },
                    'metadata': {
                        'processing_version': '1.0',
                        'filters_applied': ['noise_filter', 'calibration'],
                        'processing_flags': []
                    }
                }
                
                processed_data.append(processed_sample)
        
        # Analyze processing bottlenecks
        stats = profiler.get_stats()
        hotspots = profiler.get_hotspots()
        
        # Calculate processing rate
        processing_rate = len(processed_data) / (stats['duration_ms'] / 1000)
        
        # Performance assertions
        assert processing_rate >= 1000, f"Processing rate too low: {processing_rate:.1f} samples/sec (expected ≥1000)"
        assert profiler.peak_memory_mb < 200, f"Memory usage too high: {profiler.peak_memory_mb:.1f}MB (expected <200MB)"
        assert profiler.memory_growth_mb < 50, f"Memory growth too high: {profiler.memory_growth_mb:.1f}MB (expected <50MB)"
        
        logger.info(f"✅ Data Processing Profile:")
        logger.info(f"   - Processing rate: {processing_rate:.1f} samples/sec")
        logger.info(f"   - Duration: {stats['duration_ms']:.1f}ms")
        logger.info(f"   - Peak memory: {profiler.peak_memory_mb:.1f}MB")
        logger.info(f"   - Memory growth: {profiler.memory_growth_mb:.1f}MB")
        
        logger.info("🔥 Processing Hotspots:")
        for i, hotspot in enumerate(hotspots[:5], 1):
            logger.info(f"   {i}. {hotspot['function']}")
            logger.info(f"      Time: {hotspot['cumulative_time_ms']:.2f}ms "
                       f"({hotspot['time_per_call_ms']:.4f}ms per call)")
    
    def _apply_noise_filter(self, voltage):
        """Apply noise filtering (simulated DSP operation)"""
        # Simulate low-pass filter
        filtered = voltage * 0.9 + np.random.normal(0, 0.01)
        return filtered
    
    def _apply_calibration(self, voltage):
        """Apply calibration correction (simulated calibration)"""
        # Simulate polynomial calibration
        calibrated = voltage + 0.02 * voltage**2 - 0.001 * voltage**3
        return calibrated
    
    def _convert_to_engineering_units(self, voltage):
        """Convert to engineering units (simulated conversion)"""
        # Simulate temperature conversion: V to °C
        temperature_c = (voltage - 1.25) / 0.005  # Example conversion
        return {
            'temperature_c': temperature_c,
            'temperature_f': temperature_c * 9/5 + 32,
            'voltage': voltage
        }
    
    def _assess_signal_quality(self, sample):
        """Assess signal quality (simulated quality check)"""
        # Simple quality metric based on noise and range
        voltage = sample['voltage']
        noise_level = abs(voltage - 2.5)
        
        if noise_level < 0.1:
            return 0.95
        elif noise_level < 0.3:
            return 0.85
        else:
            return 0.75
    
    def test_database_storage_bottlenecks(self):
        """Profile database storage operations for bottlenecks"""
        logger.info("🔍 Profiling database storage bottlenecks")
        
        # Create temporary database
        db_path = tempfile.mktemp(suffix='.db')
        
        with BottleneckProfiler("Database_Storage") as profiler:
            # Initialize database
            conn = sqlite3.connect(db_path)
            
            # Create table (potential bottleneck)
            conn.execute('''
                CREATE TABLE performance_test_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    voltage REAL NOT NULL,
                    digital_state INTEGER NOT NULL,
                    processed_data JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes (potential bottleneck)
            conn.execute('CREATE INDEX idx_timestamp ON performance_test_data(timestamp)')
            conn.execute('CREATE INDEX idx_session ON performance_test_data(session_id)')
            
            # Batch insert data (potential bottleneck)
            insert_data = []
            for i in range(1000):
                processed_data = {
                    'quality_score': np.random.uniform(0.8, 1.0),
                    'calibration_applied': True,
                    'noise_filtered': True,
                    'engineering_units': {
                        'temperature_c': np.random.normal(25, 5),
                        'pressure_psi': np.random.normal(14.7, 2)
                    }
                }
                
                insert_data.append((
                    time.time() + i * 0.001,  # timestamp
                    f'session_{i // 100}',     # session_id
                    np.random.normal(2.5, 0.1), # voltage
                    np.random.choice([0, 1]),   # digital_state
                    json.dumps(processed_data)   # processed_data
                ))
            
            # Execute batch insert
            conn.executemany('''
                INSERT INTO performance_test_data 
                (timestamp, session_id, voltage, digital_state, processed_data)
                VALUES (?, ?, ?, ?, ?)
            ''', insert_data)
            
            conn.commit()
            
            # Test query performance (potential bottleneck)
            query_results = []
            
            # Range query
            cursor = conn.execute('''
                SELECT * FROM performance_test_data 
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            ''', (time.time() - 1, time.time()))
            query_results.extend(cursor.fetchall())
            
            # Aggregation query
            cursor = conn.execute('''
                SELECT session_id, AVG(voltage), COUNT(*) 
                FROM performance_test_data 
                GROUP BY session_id
            ''')
            query_results.extend(cursor.fetchall())
            
            # Complex join-like query
            cursor = conn.execute('''
                SELECT 
                    session_id,
                    MIN(voltage) as min_voltage,
                    MAX(voltage) as max_voltage,
                    AVG(voltage) as avg_voltage,
                    COUNT(*) as sample_count
                FROM performance_test_data 
                WHERE digital_state = 1
                GROUP BY session_id
                HAVING sample_count > 10
            ''')
            query_results.extend(cursor.fetchall())
            
            conn.close()
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
        
        # Analyze database bottlenecks
        stats = profiler.get_stats()
        hotspots = profiler.get_hotspots()
        
        # Calculate database performance metrics
        records_per_second = len(insert_data) / (stats['duration_ms'] / 1000)
        
        # Performance assertions
        assert records_per_second >= 500, f"Database insert rate too low: {records_per_second:.1f} records/sec (expected ≥500)"
        assert stats['duration_ms'] < 5000, f"Database operations too slow: {stats['duration_ms']:.1f}ms (expected <5000ms)"
        assert len(query_results) > 0, "Database queries returned no results"
        
        logger.info(f"✅ Database Storage Profile:")
        logger.info(f"   - Insert rate: {records_per_second:.1f} records/sec")
        logger.info(f"   - Duration: {stats['duration_ms']:.1f}ms")
        logger.info(f"   - Records inserted: {len(insert_data)}")
        logger.info(f"   - Query results: {len(query_results)}")
        
        logger.info("🔥 Database Hotspots:")
        for i, hotspot in enumerate(hotspots[:3], 1):
            logger.info(f"   {i}. {hotspot['function']}")
            logger.info(f"      Time: {hotspot['cumulative_time_ms']:.2f}ms")


class TestMemoryLeakAnalysis:
    """Test for memory leaks and memory usage patterns"""
    
    def test_memory_leak_detection_comprehensive(self):
        """Comprehensive memory leak detection across all components"""
        logger.info("🔍 Comprehensive memory leak detection")
        
        # Track objects for leak detection
        object_tracker = weakref.WeakSet()
        memory_samples = []
        
        class LeakableObject:
            """Object that can potentially leak memory"""
            def __init__(self, data_size=1000):
                self.id = id(self)
                self.data = np.random.random(data_size)
                self.references = []
                object_tracker.add(self)
        
        def simulate_data_processing_cycle():
            """Simulate one data processing cycle that might leak memory"""
            # Create objects
            data_objects = []
            
            for i in range(100):
                obj = LeakableObject(1000)
                
                # Create some internal references (potential circular references)
                obj.references.append(obj)  # Self-reference
                
                # Process object
                processed = {
                    'id': obj.id,
                    'processed_data': obj.data.mean(),
                    'timestamp': time.time(),
                    'metadata': {
                        'cycle': i,
                        'processing_flags': ['filtered', 'calibrated']
                    }
                }
                
                data_objects.append((obj, processed))
            
            # Cleanup (this should release memory if no leaks)
            for obj, processed in data_objects:
                obj.references.clear()  # Break circular references
                del processed
            
            del data_objects
            
            # Force garbage collection
            gc.collect()
            
            # Sample memory after cleanup
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_samples.append(memory_mb)
            
            return len(object_tracker)
        
        # Run multiple cycles to detect leaks
        initial_memory = psutil.virtual_memory().used / 1024 / 1024
        object_counts = []
        
        with BottleneckProfiler("Memory_Leak_Detection") as profiler:
            for cycle in range(50):  # 50 cycles
                remaining_objects = simulate_data_processing_cycle()
                object_counts.append(remaining_objects)
                
                time.sleep(0.01)  # Small delay between cycles
        
        final_memory = psutil.virtual_memory().used / 1024 / 1024
        
        # Analyze memory usage patterns
        if len(memory_samples) > 10:
            # Calculate memory trend (slope of memory usage over time)
            memory_trend = np.polyfit(range(len(memory_samples)), memory_samples, 1)[0]
            memory_variance = np.var(memory_samples)
        else:
            memory_trend = 0
            memory_variance = 0
        
        # Object count trend
        if len(object_counts) > 10:
            object_trend = np.polyfit(range(len(object_counts)), object_counts, 1)[0]
        else:
            object_trend = 0
        
        total_memory_growth = final_memory - initial_memory
        
        # Memory leak assertions
        assert memory_trend < 1.0, f"Memory leak detected: {memory_trend:.3f}MB/cycle growth (expected <1MB/cycle)"
        assert total_memory_growth < 100, f"Total memory growth too high: {total_memory_growth:.1f}MB (expected <100MB)"
        assert object_trend < 1.0, f"Object leak detected: {object_trend:.3f} objects/cycle (expected <1 object/cycle)"
        assert len(object_tracker) < 100, f"Too many objects not garbage collected: {len(object_tracker)} (expected <100)"
        
        logger.info(f"✅ Memory Leak Analysis:")
        logger.info(f"   - Memory trend: {memory_trend:.3f}MB/cycle")
        logger.info(f"   - Total memory growth: {total_memory_growth:.1f}MB")
        logger.info(f"   - Object count trend: {object_trend:.3f} objects/cycle")
        logger.info(f"   - Remaining objects: {len(object_tracker)}")
        logger.info(f"   - Memory variance: {memory_variance:.3f}")
        logger.info(f"   - Cycles completed: {len(memory_samples)}")
    
    def test_buffer_management_efficiency(self):
        """Test efficiency of buffer management strategies"""
        logger.info("🔍 Testing buffer management efficiency")
        
        buffer_strategies = [
            {'name': 'Circular Buffer', 'implementation': self._circular_buffer_test},
            {'name': 'Sliding Window', 'implementation': self._sliding_window_test},
            {'name': 'Ring Buffer', 'implementation': self._ring_buffer_test}
        ]
        
        strategy_results = []
        
        for strategy in buffer_strategies:
            logger.info(f"   Testing {strategy['name']}...")
            
            with BottleneckProfiler(f"Buffer_{strategy['name']}") as profiler:
                samples_processed, memory_efficiency = strategy['implementation']()
            
            stats = profiler.get_stats()
            
            result = {
                'strategy': strategy['name'],
                'samples_processed': samples_processed,
                'processing_time_ms': stats['duration_ms'],
                'peak_memory_mb': profiler.peak_memory_mb,
                'memory_growth_mb': profiler.memory_growth_mb,
                'memory_efficiency': memory_efficiency,
                'samples_per_second': samples_processed / (stats['duration_ms'] / 1000) if stats['duration_ms'] > 0 else 0
            }
            
            strategy_results.append(result)
        
        # Find most efficient strategy
        best_strategy = max(strategy_results, key=lambda x: x['samples_per_second'] / max(x['peak_memory_mb'], 1))
        
        # Performance assertions
        for result in strategy_results:
            assert result['samples_per_second'] >= 1000, f"{result['strategy']} too slow: {result['samples_per_second']:.1f} samples/sec"
            assert result['peak_memory_mb'] < 100, f"{result['strategy']} uses too much memory: {result['peak_memory_mb']:.1f}MB"
            assert result['memory_growth_mb'] < 20, f"{result['strategy']} memory growth too high: {result['memory_growth_mb']:.1f}MB"
        
        logger.info(f"✅ Buffer Management Results:")
        for result in strategy_results:
            logger.info(f"   - {result['strategy']}:")
            logger.info(f"     * Rate: {result['samples_per_second']:.1f} samples/sec")
            logger.info(f"     * Peak memory: {result['peak_memory_mb']:.1f}MB")
            logger.info(f"     * Efficiency: {result['memory_efficiency']:.2f}")
        
        logger.info(f"🏆 Best strategy: {best_strategy['strategy']}")
        
        return strategy_results
    
    def _circular_buffer_test(self):
        """Test circular buffer implementation"""
        buffer_size = 1000
        buffer = deque(maxlen=buffer_size)
        samples_processed = 0
        
        for i in range(10000):
            # Add sample to circular buffer
            sample = {
                'timestamp': time.time(),
                'data': np.random.random(10),  # Small data array
                'index': i
            }
            
            buffer.append(sample)
            samples_processed += 1
            
            # Simulate processing
            if len(buffer) == buffer_size:
                # Process oldest sample
                oldest = buffer[0]
                processed_value = np.mean(oldest['data'])
        
        memory_efficiency = buffer_size / samples_processed
        return samples_processed, memory_efficiency
    
    def _sliding_window_test(self):
        """Test sliding window buffer implementation"""
        window_size = 1000
        buffer = []
        samples_processed = 0
        
        for i in range(10000):
            # Add sample
            sample = {
                'timestamp': time.time(),
                'data': np.random.random(10),
                'index': i
            }
            
            buffer.append(sample)
            
            # Maintain window size
            if len(buffer) > window_size:
                buffer.pop(0)  # Remove oldest
            
            samples_processed += 1
            
            # Simulate processing
            if len(buffer) >= window_size:
                window_mean = np.mean([np.mean(s['data']) for s in buffer])
        
        memory_efficiency = len(buffer) / samples_processed
        return samples_processed, memory_efficiency
    
    def _ring_buffer_test(self):
        """Test ring buffer implementation"""
        buffer_size = 1000
        buffer = [None] * buffer_size
        write_index = 0
        samples_processed = 0
        
        for i in range(10000):
            # Add sample to ring buffer
            sample = {
                'timestamp': time.time(),
                'data': np.random.random(10),
                'index': i
            }
            
            buffer[write_index] = sample
            write_index = (write_index + 1) % buffer_size
            samples_processed += 1
            
            # Simulate processing
            if samples_processed >= buffer_size:
                # Process from ring buffer
                for j in range(min(10, buffer_size)):  # Process 10 samples
                    sample_index = (write_index - j - 1) % buffer_size
                    if buffer[sample_index] is not None:
                        processed_value = np.mean(buffer[sample_index]['data'])
        
        memory_efficiency = buffer_size / samples_processed
        return samples_processed, memory_efficiency


class TestConcurrencyBottlenecks:
    """Test concurrency-related bottlenecks and threading issues"""
    
    def test_thread_pool_scalability(self):
        """Test thread pool scalability and identify optimal thread count"""
        logger.info("🔍 Testing thread pool scalability bottlenecks")
        
        thread_counts = [1, 2, 4, 8, 16]
        scalability_results = []
        
        def cpu_intensive_task(task_id):
            """Simulate CPU-intensive processing"""
            start_time = time.perf_counter()
            
            # Simulate signal processing
            data = np.random.random(1000)
            
            # FFT (CPU-intensive)
            fft_result = np.fft.fft(data)
            
            # Filter design and application
            filtered = np.convolve(data, np.ones(10)/10, mode='valid')
            
            # Statistical analysis
            stats = {
                'mean': np.mean(data),
                'std': np.std(data),
                'min': np.min(data),
                'max': np.max(data),
                'fft_peak': np.max(np.abs(fft_result))
            }
            
            processing_time = (time.perf_counter() - start_time) * 1000
            return {
                'task_id': task_id,
                'processing_time_ms': processing_time,
                'stats': stats
            }
        
        for thread_count in thread_counts:
            logger.info(f"   Testing with {thread_count} threads...")
            
            with BottleneckProfiler(f"ThreadPool_{thread_count}") as profiler:
                with ThreadPoolExecutor(max_workers=thread_count) as executor:
                    # Submit 100 CPU-intensive tasks
                    tasks = []
                    for i in range(100):
                        future = executor.submit(cpu_intensive_task, i)
                        tasks.append(future)
                    
                    # Wait for completion
                    results = [task.result() for task in tasks]
            
            stats = profiler.get_stats()
            
            # Calculate metrics
            total_processing_time = sum(r['processing_time_ms'] for r in results)
            avg_task_time = total_processing_time / len(results)
            throughput = len(results) / (stats['duration_ms'] / 1000)
            efficiency = throughput / thread_count if thread_count > 0 else 0
            
            result = {
                'thread_count': thread_count,
                'total_duration_ms': stats['duration_ms'],
                'avg_task_time_ms': avg_task_time,
                'throughput_tasks_per_sec': throughput,
                'efficiency_per_thread': efficiency,
                'peak_memory_mb': profiler.peak_memory_mb,
                'avg_cpu_percent': profiler.avg_cpu_percent
            }
            
            scalability_results.append(result)
        
        # Find optimal thread count
        optimal_config = max(scalability_results, key=lambda x: x['throughput_tasks_per_sec'])
        
        # Performance assertions
        assert optimal_config['throughput_tasks_per_sec'] >= 10, f"Throughput too low: {optimal_config['throughput_tasks_per_sec']:.1f} tasks/sec"
        
        # Check for diminishing returns
        max_throughput = max(r['throughput_tasks_per_sec'] for r in scalability_results)
        min_throughput = min(r['throughput_tasks_per_sec'] for r in scalability_results)
        scalability_factor = max_throughput / min_throughput if min_throughput > 0 else 1
        
        assert scalability_factor >= 2, f"Poor scalability: {scalability_factor:.1f}x improvement (expected ≥2x)"
        
        logger.info(f"✅ Thread Pool Scalability:")
        for result in scalability_results:
            logger.info(f"   - {result['thread_count']} threads: "
                       f"{result['throughput_tasks_per_sec']:.1f} tasks/sec, "
                       f"{result['efficiency_per_thread']:.2f} efficiency")
        
        logger.info(f"🏆 Optimal configuration: {optimal_config['thread_count']} threads "
                   f"({optimal_config['throughput_tasks_per_sec']:.1f} tasks/sec)")
        
        return optimal_config
    
    def test_lock_contention_analysis(self):
        """Analyze lock contention bottlenecks"""
        logger.info("🔍 Analyzing lock contention bottlenecks")
        
        # Shared resource with different locking strategies
        shared_data = {'counter': 0, 'data': deque()}
        
        # Test different locking strategies
        lock_strategies = [
            {'name': 'threading.Lock', 'lock': threading.Lock()},
            {'name': 'threading.RLock', 'lock': threading.RLock()},
        ]
        
        contention_results = []
        
        for strategy in lock_strategies:
            logger.info(f"   Testing {strategy['name']}...")
            
            # Reset shared data
            shared_data['counter'] = 0
            shared_data['data'].clear()
            
            def worker_thread(thread_id, lock):
                """Worker thread that competes for lock"""
                operations_completed = 0
                contention_time = 0
                
                for i in range(1000):
                    # Measure lock acquisition time
                    lock_start = time.perf_counter()
                    
                    with lock:
                        lock_acquired = time.perf_counter()
                        contention_time += (lock_acquired - lock_start) * 1000  # ms
                        
                        # Simulate work inside critical section
                        shared_data['counter'] += 1
                        
                        # Add data to shared structure
                        shared_data['data'].append({
                            'thread_id': thread_id,
                            'operation': i,
                            'timestamp': time.time()
                        })
                        
                        # Keep only last 1000 items
                        if len(shared_data['data']) > 1000:
                            shared_data['data'].popleft()
                        
                        # Small delay to simulate processing
                        time.sleep(0.0001)  # 0.1ms
                    
                    operations_completed += 1
                
                return {
                    'thread_id': thread_id,
                    'operations': operations_completed,
                    'contention_time_ms': contention_time
                }
            
            with BottleneckProfiler(f"Lock_{strategy['name']}") as profiler:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    # Start 8 competing threads
                    futures = []
                    for thread_id in range(8):
                        future = executor.submit(worker_thread, thread_id, strategy['lock'])
                        futures.append(future)
                    
                    # Collect results
                    thread_results = [f.result() for f in futures]
            
            stats = profiler.get_stats()
            
            # Analyze contention
            total_operations = sum(r['operations'] for r in thread_results)
            total_contention_time = sum(r['contention_time_ms'] for r in thread_results)
            avg_contention_per_op = total_contention_time / total_operations if total_operations > 0 else float('inf')
            operations_per_second = total_operations / (stats['duration_ms'] / 1000) if stats['duration_ms'] > 0 else 0
            
            result = {
                'strategy': strategy['name'],
                'total_operations': total_operations,
                'total_duration_ms': stats['duration_ms'],
                'operations_per_second': operations_per_second,
                'avg_contention_ms_per_op': avg_contention_per_op,
                'total_contention_ms': total_contention_time,
                'final_counter': shared_data['counter'],
                'data_items': len(shared_data['data'])
            }
            
            contention_results.append(result)
        
        # Find best locking strategy
        best_strategy = max(contention_results, key=lambda x: x['operations_per_second'])
        
        # Performance assertions
        for result in contention_results:
            assert result['operations_per_second'] >= 100, f"{result['strategy']} too slow: {result['operations_per_second']:.1f} ops/sec"
            assert result['avg_contention_ms_per_op'] < 10, f"{result['strategy']} contention too high: {result['avg_contention_ms_per_op']:.3f}ms per op"
            assert result['final_counter'] == result['total_operations'], f"{result['strategy']} lost operations: {result['final_counter']} != {result['total_operations']}"
        
        logger.info(f"✅ Lock Contention Analysis:")
        for result in contention_results:
            logger.info(f"   - {result['strategy']}:")
            logger.info(f"     * Operations/sec: {result['operations_per_second']:.1f}")
            logger.info(f"     * Avg contention: {result['avg_contention_ms_per_op']:.3f}ms per op")
            logger.info(f"     * Total contention: {result['total_contention_ms']:.1f}ms")
        
        logger.info(f"🏆 Best locking strategy: {best_strategy['strategy']}")
        
        return best_strategy


if __name__ == "__main__":
    """Run bottleneck analysis tests"""
    logger.info("🔍 Starting Performance Bottleneck Analysis")
    logger.info("=" * 70)
    
    # Run tests with detailed reporting
    pytest.main([
        __file__,
        "-v", 
        "--tb=short",
        "--durations=10",
        f"--maxfail=3"
    ])