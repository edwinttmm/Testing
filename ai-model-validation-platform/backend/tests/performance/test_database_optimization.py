#!/usr/bin/env python3
"""
Database Query Optimization and Performance Testing

This test suite focuses on optimizing database queries for the hybrid LabJack
logging system, with emphasis on hybrid data access patterns and indexing strategies.

Author: Claude Code Database Optimization Agent
Date: 2025-01-24
"""

import pytest
import sqlite3
import time
import json
import numpy as np
import os
import sys
import threading
import tempfile
import logging
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import List, Dict, Any, Tuple
import psutil

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Database optimization and performance testing utility"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or tempfile.mktemp(suffix='.db')
        self.connection = None
        self.query_stats = {}
        self.index_stats = {}
        
    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row  # Enable column access by name
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
        
        # Cleanup temp file
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except:
            pass
    
    def create_hybrid_schema(self):
        """Create optimized schema for hybrid data storage"""
        
        # Raw data table (high-frequency, recent data)
        self.connection.execute('''
            CREATE TABLE raw_labjack_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                timestamp_ns TEXT,
                session_id TEXT NOT NULL,
                voltage REAL NOT NULL,
                digital_state INTEGER NOT NULL,
                sample_rate INTEGER DEFAULT 1000,
                quality_score REAL DEFAULT 1.0,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Compressed data table (historical, batch-processed data)
        self.connection.execute('''
            CREATE TABLE compressed_labjack_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_start REAL NOT NULL,
                timestamp_end REAL NOT NULL,
                session_id TEXT NOT NULL,
                compressed_data BLOB NOT NULL,
                compression_method TEXT NOT NULL,
                compression_ratio REAL NOT NULL,
                sample_count INTEGER NOT NULL,
                original_size_bytes INTEGER NOT NULL,
                compressed_size_bytes INTEGER NOT NULL,
                quality_metrics JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Session metadata table
        self.connection.execute('''
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL,
                sample_rate INTEGER DEFAULT 1000,
                total_samples INTEGER DEFAULT 0,
                compression_enabled BOOLEAN DEFAULT TRUE,
                status TEXT DEFAULT 'active',
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Performance metrics table
        self.connection.execute('''
            CREATE TABLE performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                metric_type TEXT NOT NULL,
                metric_value REAL NOT NULL,
                session_id TEXT,
                details JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.connection.commit()
    
    def create_optimized_indexes(self):
        """Create optimized indexes for hybrid query patterns"""
        
        # Raw data indexes
        indexes = [
            # Time-based queries
            ('idx_raw_timestamp', 'raw_labjack_data', 'timestamp'),
            ('idx_raw_timestamp_desc', 'raw_labjack_data', 'timestamp DESC'),
            
            # Session-based queries  
            ('idx_raw_session', 'raw_labjack_data', 'session_id'),
            ('idx_raw_session_timestamp', 'raw_labjack_data', 'session_id, timestamp'),
            
            # Quality-based queries
            ('idx_raw_quality', 'raw_labjack_data', 'quality_score'),
            
            # Compressed data indexes
            ('idx_compressed_start', 'compressed_labjack_data', 'timestamp_start'),
            ('idx_compressed_end', 'compressed_labjack_data', 'timestamp_end'),
            ('idx_compressed_session', 'compressed_labjack_data', 'session_id'),
            ('idx_compressed_session_time', 'compressed_labjack_data', 'session_id, timestamp_start'),
            ('idx_compressed_ratio', 'compressed_labjack_data', 'compression_ratio'),
            
            # Session indexes
            ('idx_sessions_start', 'sessions', 'start_time'),
            ('idx_sessions_status', 'sessions', 'status'),
            
            # Performance metrics indexes
            ('idx_metrics_timestamp', 'performance_metrics', 'timestamp'),
            ('idx_metrics_type', 'performance_metrics', 'metric_type'),
            ('idx_metrics_session', 'performance_metrics', 'session_id')
        ]
        
        for index_name, table, columns in indexes:
            try:
                sql = f'CREATE INDEX {index_name} ON {table}({columns})'
                start_time = time.perf_counter()
                self.connection.execute(sql)
                create_time = (time.perf_counter() - start_time) * 1000
                
                self.index_stats[index_name] = {
                    'table': table,
                    'columns': columns,
                    'create_time_ms': create_time
                }
                
                logger.debug(f"Created index {index_name} in {create_time:.2f}ms")
                
            except sqlite3.Error as e:
                logger.warning(f"Failed to create index {index_name}: {e}")
        
        self.connection.commit()
    
    def populate_test_data(self, raw_samples: int = 50000, compressed_batches: int = 1000):
        """Populate database with realistic test data"""
        logger.info(f"Populating test data: {raw_samples} raw samples, {compressed_batches} compressed batches")
        
        # Generate sessions
        sessions = []
        for i in range(5):  # 5 test sessions
            session_id = f"session_{i:03d}"
            start_time = time.time() - 3600 * (i + 1)  # Sessions from 1-5 hours ago
            
            session = (
                session_id,
                f"HIL Test Session {i+1}",
                start_time,
                start_time + 1800,  # 30 minutes each
                1000,  # sample_rate
                raw_samples // 5,  # samples per session
                True,  # compression_enabled
                'completed',
                json.dumps({'test_type': 'hil', 'hardware': 'labjack_t7'})
            )
            sessions.append(session)
        
        self.connection.executemany('''
            INSERT INTO sessions 
            (id, name, start_time, end_time, sample_rate, total_samples, compression_enabled, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sessions)
        
        # Generate raw data (recent, high-frequency)
        raw_data = []
        current_time = time.time()
        
        for i in range(raw_samples):
            session_id = f"session_{i % 5:03d}"
            timestamp = current_time - (raw_samples - i) * 0.001  # 1000Hz backwards
            
            # Generate realistic signal
            voltage = 2.5 + 0.5 * np.sin(2 * np.pi * 10 * timestamp)  # 10Hz sine wave
            voltage += np.random.normal(0, 0.05)  # Add noise
            
            digital_state = int((i % 200) < 100)  # 50% duty cycle every 200ms
            quality_score = max(0.8, 1.0 - abs(voltage - 2.5) / 2.0)  # Quality based on signal
            
            metadata = {
                'calibration_applied': True,
                'filter_type': 'lowpass',
                'sample_number': i
            }
            
            raw_sample = (
                timestamp,
                f"{timestamp:.9f}",  # timestamp_ns
                session_id,
                voltage,
                digital_state,
                1000,  # sample_rate
                quality_score,
                json.dumps(metadata)
            )
            raw_data.append(raw_sample)
        
        # Batch insert raw data for performance
        batch_size = 1000
        for i in range(0, len(raw_data), batch_size):
            batch = raw_data[i:i + batch_size]
            self.connection.executemany('''
                INSERT INTO raw_labjack_data 
                (timestamp, timestamp_ns, session_id, voltage, digital_state, sample_rate, quality_score, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch)
            
            if i % (batch_size * 10) == 0:
                self.connection.commit()  # Periodic commits
        
        # Generate compressed data (historical)
        compressed_data = []
        base_time = current_time - 7200  # 2 hours ago
        
        for i in range(compressed_batches):
            session_id = f"session_{i % 5:03d}"
            timestamp_start = base_time + i * 10  # 10-second intervals
            timestamp_end = timestamp_start + 10
            
            # Simulate compressed data (Delta compression example)
            original_samples = np.random.normal(2.5, 0.2, 10000)  # 10k samples
            compressed_samples = self._simulate_delta_compression(original_samples)
            compressed_blob = json.dumps(compressed_samples).encode()
            
            original_size = len(original_samples) * 8  # 8 bytes per float64
            compressed_size = len(compressed_blob)
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            
            quality_metrics = {
                'signal_to_noise_ratio': np.random.uniform(20, 40),
                'peak_to_peak': np.ptp(original_samples),
                'rms': np.sqrt(np.mean(original_samples**2))
            }
            
            compressed_sample = (
                timestamp_start,
                timestamp_end,
                session_id,
                compressed_blob,
                'delta_compression',
                compression_ratio,
                len(original_samples),
                original_size,
                compressed_size,
                json.dumps(quality_metrics)
            )
            compressed_data.append(compressed_sample)
        
        self.connection.executemany('''
            INSERT INTO compressed_labjack_data
            (timestamp_start, timestamp_end, session_id, compressed_data, compression_method, 
             compression_ratio, sample_count, original_size_bytes, compressed_size_bytes, quality_metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', compressed_data)
        
        self.connection.commit()
        logger.info("Test data population completed")
    
    def _simulate_delta_compression(self, samples):
        """Simulate delta compression for test data"""
        if len(samples) == 0:
            return []
        
        compressed = [samples[0]]  # First sample
        threshold = 0.01
        
        for i in range(1, len(samples)):
            if abs(samples[i] - compressed[-1]) > threshold:
                compressed.append(samples[i])
        
        return compressed
    
    @contextmanager
    def measure_query(self, query_name: str):
        """Context manager to measure query performance"""
        start_time = time.perf_counter()
        start_memory = psutil.Process().memory_info().rss
        
        yield
        
        end_time = time.perf_counter()
        end_memory = psutil.Process().memory_info().rss
        
        execution_time = (end_time - start_time) * 1000  # ms
        memory_delta = (end_memory - start_memory) / 1024 / 1024  # MB
        
        self.query_stats[query_name] = {
            'execution_time_ms': execution_time,
            'memory_delta_mb': memory_delta,
            'timestamp': datetime.now()
        }
    
    def get_query_plan(self, sql: str):
        """Get SQLite query execution plan"""
        explain_sql = f"EXPLAIN QUERY PLAN {sql}"
        cursor = self.connection.execute(explain_sql)
        plan = cursor.fetchall()
        return [dict(row) for row in plan]
    
    def analyze_index_usage(self, sql: str):
        """Analyze index usage for a query"""
        plan = self.get_query_plan(sql)
        
        index_info = {
            'uses_index': False,
            'indexes_used': [],
            'table_scans': [],
            'plan_details': plan
        }
        
        for step in plan:
            detail = step.get('detail', '').lower()
            
            if 'using index' in detail:
                index_info['uses_index'] = True
                # Extract index name
                if 'index ' in detail:
                    index_start = detail.find('index ') + 6
                    index_end = detail.find(' ', index_start)
                    index_name = detail[index_start:index_end] if index_end > 0 else detail[index_start:]
                    index_info['indexes_used'].append(index_name)
            
            if 'scan table' in detail:
                table_start = detail.find('scan table ') + 11
                table_end = detail.find(' ', table_start)
                table_name = detail[table_start:table_end] if table_end > 0 else detail[table_start:]
                index_info['table_scans'].append(table_name)
        
        return index_info


class TestHybridQueryOptimization:
    """Test hybrid query patterns and optimization"""
    
    @pytest.fixture
    def optimized_db(self):
        """Create optimized test database"""
        with DatabaseOptimizer() as db:
            db.create_hybrid_schema()
            db.create_optimized_indexes()
            db.populate_test_data(raw_samples=10000, compressed_batches=500)
            yield db
    
    def test_recent_data_query_performance(self, optimized_db):
        """Test performance of recent data queries"""
        logger.info("🧪 Testing recent data query performance")
        
        # Test scenarios for recent data access
        test_queries = [
            {
                'name': 'Last 5 seconds',
                'sql': '''
                    SELECT timestamp, voltage, digital_state 
                    FROM raw_labjack_data 
                    WHERE timestamp > ? AND session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 5000
                ''',
                'params': (time.time() - 5, 'session_000')
            },
            {
                'name': 'Last 30 seconds aggregated',
                'sql': '''
                    SELECT 
                        AVG(voltage) as avg_voltage,
                        MIN(voltage) as min_voltage,
                        MAX(voltage) as max_voltage,
                        COUNT(*) as sample_count
                    FROM raw_labjack_data 
                    WHERE timestamp > ? AND session_id = ?
                ''',
                'params': (time.time() - 30, 'session_000')
            },
            {
                'name': 'Quality-filtered recent data',
                'sql': '''
                    SELECT timestamp, voltage, digital_state, quality_score
                    FROM raw_labjack_data 
                    WHERE timestamp > ? AND quality_score > 0.9
                    ORDER BY timestamp DESC
                    LIMIT 1000
                ''',
                'params': (time.time() - 10,)
            }
        ]
        
        query_results = []
        
        for query_info in test_queries:
            # Analyze query plan
            index_usage = optimized_db.analyze_index_usage(query_info['sql'])
            
            # Execute and measure query
            with optimized_db.measure_query(query_info['name']):
                cursor = optimized_db.connection.execute(query_info['sql'], query_info['params'])
                results = cursor.fetchall()
            
            stats = optimized_db.query_stats[query_info['name']]
            
            result_info = {
                'query_name': query_info['name'],
                'execution_time_ms': stats['execution_time_ms'],
                'memory_delta_mb': stats['memory_delta_mb'],
                'result_count': len(results),
                'uses_index': index_usage['uses_index'],
                'indexes_used': index_usage['indexes_used'],
                'table_scans': index_usage['table_scans']
            }
            
            query_results.append(result_info)
            
            # Performance assertions
            assert stats['execution_time_ms'] < 100, f"{query_info['name']} too slow: {stats['execution_time_ms']:.1f}ms (expected <100ms)"
            assert index_usage['uses_index'], f"{query_info['name']} should use index but performs table scan"
            assert len(index_usage['table_scans']) == 0, f"{query_info['name']} performs unnecessary table scans: {index_usage['table_scans']}"
        
        logger.info("✅ Recent Data Query Performance:")
        for result in query_results:
            logger.info(f"   - {result['query_name']}: {result['execution_time_ms']:.1f}ms, "
                       f"{result['result_count']} results, "
                       f"indexes: {result['indexes_used']}")
        
        return query_results
    
    def test_historical_data_query_performance(self, optimized_db):
        """Test performance of historical compressed data queries"""
        logger.info("🧪 Testing historical data query performance")
        
        test_queries = [
            {
                'name': 'Time range compressed data',
                'sql': '''
                    SELECT timestamp_start, timestamp_end, compressed_data, compression_ratio
                    FROM compressed_labjack_data
                    WHERE session_id = ? AND timestamp_start BETWEEN ? AND ?
                    ORDER BY timestamp_start
                ''',
                'params': ('session_000', time.time() - 7200, time.time() - 3600)
            },
            {
                'name': 'Compression efficiency analysis',
                'sql': '''
                    SELECT 
                        AVG(compression_ratio) as avg_ratio,
                        MIN(compression_ratio) as min_ratio,
                        MAX(compression_ratio) as max_ratio,
                        SUM(original_size_bytes) as total_original,
                        SUM(compressed_size_bytes) as total_compressed
                    FROM compressed_labjack_data
                    WHERE session_id = ?
                ''',
                'params': ('session_000',)
            },
            {
                'name': 'High compression ratio batches',
                'sql': '''
                    SELECT timestamp_start, compression_ratio, sample_count
                    FROM compressed_labjack_data
                    WHERE compression_ratio > 8.0
                    ORDER BY compression_ratio DESC
                    LIMIT 100
                ''',
                'params': ()
            }
        ]
        
        query_results = []
        
        for query_info in test_queries:
            # Analyze query plan
            index_usage = optimized_db.analyze_index_usage(query_info['sql'])
            
            # Execute and measure query
            with optimized_db.measure_query(query_info['name']):
                cursor = optimized_db.connection.execute(query_info['sql'], query_info['params'])
                results = cursor.fetchall()
            
            stats = optimized_db.query_stats[query_info['name']]
            
            result_info = {
                'query_name': query_info['name'],
                'execution_time_ms': stats['execution_time_ms'],
                'memory_delta_mb': stats['memory_delta_mb'],
                'result_count': len(results),
                'uses_index': index_usage['uses_index'],
                'indexes_used': index_usage['indexes_used']
            }
            
            query_results.append(result_info)
            
            # Performance assertions
            assert stats['execution_time_ms'] < 200, f"{query_info['name']} too slow: {stats['execution_time_ms']:.1f}ms (expected <200ms)"
        
        logger.info("✅ Historical Data Query Performance:")
        for result in query_results:
            logger.info(f"   - {result['query_name']}: {result['execution_time_ms']:.1f}ms, "
                       f"{result['result_count']} results")
        
        return query_results
    
    def test_hybrid_query_performance(self, optimized_db):
        """Test performance of hybrid queries that span both raw and compressed data"""
        logger.info("🧪 Testing hybrid query performance")
        
        # Complex hybrid query combining recent and historical data
        hybrid_query = '''
            WITH recent_data AS (
                SELECT timestamp, voltage, 'raw' as data_type
                FROM raw_labjack_data 
                WHERE session_id = ? AND timestamp > ?
            ),
            historical_summary AS (
                SELECT 
                    (timestamp_start + timestamp_end) / 2 as timestamp,
                    json_extract(quality_metrics, '$.rms') as voltage,
                    'compressed' as data_type
                FROM compressed_labjack_data
                WHERE session_id = ? AND timestamp_end < ?
            )
            SELECT * FROM (
                SELECT * FROM recent_data
                UNION ALL
                SELECT * FROM historical_summary
            )
            ORDER BY timestamp DESC
            LIMIT 10000
        '''
        
        params = ('session_000', time.time() - 60, 'session_000', time.time() - 60)
        
        # Analyze query plan
        index_usage = optimized_db.analyze_index_usage(hybrid_query)
        
        # Execute and measure hybrid query
        with optimized_db.measure_query('Hybrid Query'):
            cursor = optimized_db.connection.execute(hybrid_query, params)
            results = cursor.fetchall()
        
        stats = optimized_db.query_stats['Hybrid Query']
        
        # Performance assertions for hybrid query
        assert stats['execution_time_ms'] < 300, f"Hybrid query too slow: {stats['execution_time_ms']:.1f}ms (expected <300ms)"
        assert len(results) > 0, "Hybrid query returned no results"
        assert stats['memory_delta_mb'] < 50, f"Hybrid query uses too much memory: {stats['memory_delta_mb']:.1f}MB"
        
        # Verify data types in results
        data_types = set(row['data_type'] for row in results if row['data_type'])
        assert 'raw' in data_types or 'compressed' in data_types, "Hybrid query should return mixed data types"
        
        logger.info(f"✅ Hybrid Query Performance:")
        logger.info(f"   - Execution time: {stats['execution_time_ms']:.1f}ms")
        logger.info(f"   - Results returned: {len(results)}")
        logger.info(f"   - Memory usage: {stats['memory_delta_mb']:.1f}MB")
        logger.info(f"   - Data types: {sorted(data_types)}")
        logger.info(f"   - Uses indexes: {index_usage['uses_index']}")
        
        return {
            'execution_time_ms': stats['execution_time_ms'],
            'result_count': len(results),
            'data_types': list(data_types),
            'uses_index': index_usage['uses_index']
        }


class TestConcurrentDatabaseAccess:
    """Test database performance under concurrent access patterns"""
    
    @pytest.fixture
    def concurrent_db(self):
        """Create database for concurrent access testing"""
        with DatabaseOptimizer() as db:
            db.create_hybrid_schema()
            db.create_optimized_indexes()
            db.populate_test_data(raw_samples=5000, compressed_batches=200)
            yield db
    
    def test_concurrent_read_performance(self, concurrent_db):
        """Test concurrent read performance"""
        logger.info("🧪 Testing concurrent database read performance")
        
        def read_worker(worker_id, db_path):
            """Worker function for concurrent reads"""
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            query_times = []
            results_count = []
            
            for i in range(20):  # 20 queries per worker
                start_time = time.perf_counter()
                
                # Mix of different query types
                if i % 3 == 0:
                    # Recent data query
                    cursor = conn.execute('''
                        SELECT timestamp, voltage FROM raw_labjack_data 
                        WHERE timestamp > ? 
                        ORDER BY timestamp DESC LIMIT 100
                    ''', (time.time() - 30,))
                elif i % 3 == 1:
                    # Aggregation query
                    cursor = conn.execute('''
                        SELECT AVG(voltage), COUNT(*) FROM raw_labjack_data 
                        WHERE session_id = ?
                    ''', (f'session_{worker_id % 3:03d}',))
                else:
                    # Historical data query
                    cursor = conn.execute('''
                        SELECT compression_ratio, sample_count FROM compressed_labjack_data
                        WHERE session_id = ?
                        ORDER BY timestamp_start LIMIT 50
                    ''', (f'session_{worker_id % 3:03d}',))
                
                results = cursor.fetchall()
                query_time = (time.perf_counter() - start_time) * 1000
                
                query_times.append(query_time)
                results_count.append(len(results))
                
                # Small delay between queries
                time.sleep(0.01)
            
            conn.close()
            
            return {
                'worker_id': worker_id,
                'avg_query_time_ms': np.mean(query_times),
                'max_query_time_ms': np.max(query_times),
                'total_results': sum(results_count),
                'queries_completed': len(query_times)
            }
        
        # Run concurrent read workers
        num_workers = 8
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(read_worker, i, concurrent_db.db_path)
                for i in range(num_workers)
            ]
            
            worker_results = [future.result() for future in as_completed(futures)]
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        # Analyze concurrent read performance
        avg_query_times = [r['avg_query_time_ms'] for r in worker_results]
        max_query_times = [r['max_query_time_ms'] for r in worker_results]
        total_queries = sum(r['queries_completed'] for r in worker_results)
        
        overall_avg_time = np.mean(avg_query_times)
        overall_max_time = np.max(max_query_times)
        queries_per_second = total_queries / (total_time / 1000) if total_time > 0 else 0
        
        # Performance assertions
        assert overall_avg_time < 150, f"Concurrent read average too slow: {overall_avg_time:.1f}ms (expected <150ms)"
        assert overall_max_time < 500, f"Concurrent read max too slow: {overall_max_time:.1f}ms (expected <500ms)"
        assert queries_per_second >= 50, f"Concurrent throughput too low: {queries_per_second:.1f} queries/sec (expected ≥50)"
        
        logger.info(f"✅ Concurrent Read Performance:")
        logger.info(f"   - Workers: {num_workers}")
        logger.info(f"   - Total queries: {total_queries}")
        logger.info(f"   - Queries per second: {queries_per_second:.1f}")
        logger.info(f"   - Average query time: {overall_avg_time:.1f}ms")
        logger.info(f"   - Maximum query time: {overall_max_time:.1f}ms")
        logger.info(f"   - Total execution time: {total_time:.1f}ms")
        
        return {
            'queries_per_second': queries_per_second,
            'avg_query_time_ms': overall_avg_time,
            'max_query_time_ms': overall_max_time
        }
    
    def test_mixed_read_write_performance(self, concurrent_db):
        """Test performance under mixed read/write workload"""
        logger.info("🧪 Testing mixed read/write database performance")
        
        def write_worker(worker_id, db_path):
            """Worker function for database writes"""
            conn = sqlite3.connect(db_path)
            
            writes_completed = 0
            write_times = []
            
            for i in range(100):  # 100 writes per worker
                start_time = time.perf_counter()
                
                # Insert new raw data
                timestamp = time.time() + i * 0.001
                voltage = 2.5 + np.random.normal(0, 0.1)
                digital_state = np.random.choice([0, 1])
                session_id = f'session_{worker_id % 3:03d}'
                
                conn.execute('''
                    INSERT INTO raw_labjack_data 
                    (timestamp, session_id, voltage, digital_state, quality_score)
                    VALUES (?, ?, ?, ?, ?)
                ''', (timestamp, session_id, voltage, digital_state, 0.95))
                
                if i % 10 == 0:  # Commit every 10 writes
                    conn.commit()
                
                write_time = (time.perf_counter() - start_time) * 1000
                write_times.append(write_time)
                writes_completed += 1
                
                time.sleep(0.005)  # 5ms delay between writes
            
            conn.commit()
            conn.close()
            
            return {
                'worker_id': worker_id,
                'writes_completed': writes_completed,
                'avg_write_time_ms': np.mean(write_times) if write_times else 0,
                'max_write_time_ms': np.max(write_times) if write_times else 0
            }
        
        def read_worker(worker_id, db_path):
            """Worker function for concurrent reads during writes"""
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            
            reads_completed = 0
            read_times = []
            
            for i in range(150):  # More reads than writes
                start_time = time.perf_counter()
                
                # Read recent data
                cursor = conn.execute('''
                    SELECT COUNT(*), AVG(voltage) FROM raw_labjack_data 
                    WHERE timestamp > ?
                ''', (time.time() - 60,))
                
                results = cursor.fetchall()
                
                read_time = (time.perf_counter() - start_time) * 1000
                read_times.append(read_time)
                reads_completed += 1
                
                time.sleep(0.01)  # 10ms delay between reads
            
            conn.close()
            
            return {
                'worker_id': worker_id,
                'reads_completed': reads_completed,
                'avg_read_time_ms': np.mean(read_times) if read_times else 0,
                'max_read_time_ms': np.max(read_times) if read_times else 0
            }
        
        # Run mixed workload
        num_writers = 3
        num_readers = 5
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_writers + num_readers) as executor:
            # Submit write workers
            write_futures = [
                executor.submit(write_worker, i, concurrent_db.db_path)
                for i in range(num_writers)
            ]
            
            # Submit read workers
            read_futures = [
                executor.submit(read_worker, i + num_writers, concurrent_db.db_path)
                for i in range(num_readers)
            ]
            
            # Collect results
            write_results = [future.result() for future in write_futures]
            read_results = [future.result() for future in read_futures]
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        # Analyze mixed workload performance
        total_writes = sum(r['writes_completed'] for r in write_results)
        total_reads = sum(r['reads_completed'] for r in read_results)
        
        avg_write_time = np.mean([r['avg_write_time_ms'] for r in write_results])
        avg_read_time = np.mean([r['avg_read_time_ms'] for r in read_results])
        
        writes_per_second = total_writes / (total_time / 1000) if total_time > 0 else 0
        reads_per_second = total_reads / (total_time / 1000) if total_time > 0 else 0
        
        # Performance assertions
        assert avg_write_time < 50, f"Mixed workload write time too slow: {avg_write_time:.1f}ms (expected <50ms)"
        assert avg_read_time < 100, f"Mixed workload read time too slow: {avg_read_time:.1f}ms (expected <100ms)"
        assert writes_per_second >= 10, f"Write throughput too low: {writes_per_second:.1f} writes/sec (expected ≥10)"
        assert reads_per_second >= 20, f"Read throughput too low: {reads_per_second:.1f} reads/sec (expected ≥20)"
        
        logger.info(f"✅ Mixed Read/Write Performance:")
        logger.info(f"   - Writers: {num_writers}, Readers: {num_readers}")
        logger.info(f"   - Total writes: {total_writes} ({writes_per_second:.1f}/sec)")
        logger.info(f"   - Total reads: {total_reads} ({reads_per_second:.1f}/sec)")
        logger.info(f"   - Average write time: {avg_write_time:.1f}ms")
        logger.info(f"   - Average read time: {avg_read_time:.1f}ms")
        logger.info(f"   - Total execution time: {total_time:.1f}ms")
        
        return {
            'writes_per_second': writes_per_second,
            'reads_per_second': reads_per_second,
            'avg_write_time_ms': avg_write_time,
            'avg_read_time_ms': avg_read_time
        }


if __name__ == "__main__":
    """Run database optimization tests"""
    logger.info("🗄️ Starting Database Optimization Testing")
    logger.info("=" * 60)
    
    # Run tests with detailed reporting
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--durations=10",
        f"--maxfail=3"
    ])