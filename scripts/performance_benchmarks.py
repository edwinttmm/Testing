#!/usr/bin/env python3
"""
Comprehensive Performance Benchmark Suite
AI Model Validation Platform - Performance Analysis
"""

import time
import psutil
import subprocess
import sqlite3
import requests
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import threading
import statistics

@dataclass
class PerformanceMetric:
    name: str
    value: float
    unit: str
    category: str
    timestamp: float
    details: Optional[Dict[str, Any]] = None

class PerformanceBenchmark:
    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.api_base_url = "http://localhost:8001"
        self.database_path = "./ai-model-validation-platform/backend/test_database.db"
        self.results = {}
        
    @contextmanager
    def measure_time(self, name: str, category: str):
        """Context manager to measure execution time"""
        start_time = time.time()
        start_memory = psutil.virtual_memory().used
        yield
        end_time = time.time()
        end_memory = psutil.virtual_memory().used
        
        duration = end_time - start_time
        memory_delta = end_memory - start_memory
        
        self.add_metric(name, duration, "seconds", category, {
            "memory_delta_mb": memory_delta / (1024*1024),
            "start_time": start_time,
            "end_time": end_time
        })
    
    def add_metric(self, name: str, value: float, unit: str, category: str, details: Dict = None):
        """Add a performance metric"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            category=category,
            timestamp=time.time(),
            details=details or {}
        )
        self.metrics.append(metric)
        
    def test_database_performance(self):
        """Comprehensive database performance testing"""
        print("=== DATABASE PERFORMANCE ANALYSIS ===")
        
        if not os.path.exists(self.database_path):
            print(f"Database not found at {self.database_path}")
            return
            
        # Connection performance
        connection_times = []
        for i in range(10):
            with self.measure_time(f"db_connection_{i}", "database"):
                conn = sqlite3.connect(self.database_path)
                conn.close()
            connection_times.append(self.metrics[-1].value)
        
        avg_connection_time = statistics.mean(connection_times)
        self.add_metric("avg_db_connection_time", avg_connection_time, "seconds", "database")
        
        # Query performance tests
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        queries = {
            "count_projects": "SELECT COUNT(*) FROM projects",
            "count_videos": "SELECT COUNT(*) FROM videos",
            "count_test_sessions": "SELECT COUNT(*) FROM test_sessions", 
            "count_detection_events": "SELECT COUNT(*) FROM detection_events",
            "complex_join": """
                SELECT p.name, COUNT(v.id) as video_count, COUNT(ts.id) as session_count
                FROM projects p
                LEFT JOIN videos v ON p.id = v.project_id
                LEFT JOIN test_sessions ts ON p.id = ts.project_id
                GROUP BY p.id, p.name
            """,
            "time_range_query": """
                SELECT * FROM detection_events 
                WHERE timestamp > 1000 AND timestamp < 2000
                ORDER BY timestamp DESC
                LIMIT 100
            """
        }
        
        for query_name, sql in queries.items():
            try:
                with self.measure_time(f"query_{query_name}", "database"):
                    cursor.execute(sql)
                    results = cursor.fetchall()
                    row_count = len(results)
                
                self.metrics[-1].details["rows_returned"] = row_count
                print(f"Query {query_name}: {self.metrics[-1].value:.4f}s ({row_count} rows)")
                
            except Exception as e:
                print(f"Query {query_name} failed: {e}")
                
        conn.close()
    
    def test_api_performance(self):
        """Test API endpoint performance"""
        print("\n=== API PERFORMANCE ANALYSIS ===")
        
        endpoints = [
            {"url": "/health", "method": "GET", "name": "health_check"},
            {"url": "/api/dashboard/stats", "method": "GET", "name": "dashboard_stats"},
            {"url": "/api/projects", "method": "GET", "name": "list_projects"},
            {"url": "/api/test-sessions", "method": "GET", "name": "list_test_sessions"},
        ]
        
        # Test single requests
        for endpoint in endpoints:
            url = f"{self.api_base_url}{endpoint['url']}"
            try:
                with self.measure_time(f"api_{endpoint['name']}", "api"):
                    response = requests.get(url, timeout=10)
                    
                self.metrics[-1].details.update({
                    "status_code": response.status_code,
                    "response_size": len(response.content),
                    "headers": dict(response.headers)
                })
                
                print(f"API {endpoint['name']}: {self.metrics[-1].value:.4f}s "
                      f"(Status: {response.status_code}, Size: {len(response.content)} bytes)")
                      
            except Exception as e:
                print(f"API {endpoint['name']} failed: {e}")
                self.add_metric(f"api_{endpoint['name']}_error", 0, "error", "api", {"error": str(e)})
    
    def test_concurrent_load(self):
        """Test concurrent request handling"""
        print("\n=== CONCURRENT LOAD TESTING ===")
        
        def make_request(request_id):
            url = f"{self.api_base_url}/api/dashboard/stats"
            start_time = time.time()
            try:
                response = requests.get(url, timeout=10)
                duration = time.time() - start_time
                return {
                    "request_id": request_id,
                    "duration": duration,
                    "status_code": response.status_code,
                    "success": True
                }
            except Exception as e:
                duration = time.time() - start_time
                return {
                    "request_id": request_id,
                    "duration": duration,
                    "error": str(e),
                    "success": False
                }
        
        # Test different concurrency levels
        concurrency_levels = [1, 5, 10, 20]
        requests_per_level = 50
        
        for concurrency in concurrency_levels:
            print(f"\nTesting concurrency level: {concurrency}")
            
            with self.measure_time(f"concurrent_load_{concurrency}", "load_test"):
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = [executor.submit(make_request, i) for i in range(requests_per_level)]
                    results = [future.result() for future in as_completed(futures)]
            
            # Analyze results
            successful_requests = [r for r in results if r["success"]]
            failed_requests = [r for r in results if not r["success"]]
            
            if successful_requests:
                durations = [r["duration"] for r in successful_requests]
                avg_duration = statistics.mean(durations)
                p95_duration = statistics.quantiles(durations, n=20)[18] if len(durations) > 1 else durations[0]
                throughput = len(successful_requests) / self.metrics[-1].value
                
                self.add_metric(f"concurrent_avg_response_time_{concurrency}", avg_duration, "seconds", "load_test")
                self.add_metric(f"concurrent_p95_response_time_{concurrency}", p95_duration, "seconds", "load_test")
                self.add_metric(f"concurrent_throughput_{concurrency}", throughput, "req/sec", "load_test")
                self.add_metric(f"concurrent_success_rate_{concurrency}", 
                               len(successful_requests)/len(results)*100, "percent", "load_test")
                
                print(f"  Successful: {len(successful_requests)}/{len(results)}")
                print(f"  Avg Response Time: {avg_duration:.4f}s")
                print(f"  P95 Response Time: {p95_duration:.4f}s")
                print(f"  Throughput: {throughput:.2f} req/sec")
                print(f"  Failed: {len(failed_requests)}")
    
    def test_memory_usage(self):
        """Analyze memory usage patterns"""
        print("\n=== MEMORY USAGE ANALYSIS ===")
        
        process = psutil.Process()
        
        # Initial memory state
        initial_memory = process.memory_info()
        self.add_metric("initial_rss_memory", initial_memory.rss / (1024*1024), "MB", "memory")
        self.add_metric("initial_vms_memory", initial_memory.vms / (1024*1024), "MB", "memory")
        
        # System memory
        system_memory = psutil.virtual_memory()
        self.add_metric("system_total_memory", system_memory.total / (1024*1024*1024), "GB", "memory")
        self.add_metric("system_available_memory", system_memory.available / (1024*1024*1024), "GB", "memory")
        self.add_metric("system_memory_percent", system_memory.percent, "percent", "memory")
        
        print(f"Initial RSS Memory: {initial_memory.rss / (1024*1024):.2f} MB")
        print(f"Initial VMS Memory: {initial_memory.vms / (1024*1024):.2f} MB")
        print(f"System Memory Usage: {system_memory.percent:.1f}%")
        
    def test_frontend_bundle_analysis(self):
        """Analyze frontend bundle size and composition"""
        print("\n=== FRONTEND BUNDLE ANALYSIS ===")
        
        build_path = "./ai-model-validation-platform/frontend/build"
        node_modules_path = "./ai-model-validation-platform/frontend/node_modules"
        
        # Check build directory
        if os.path.exists(build_path):
            # Get build size
            build_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(build_path)
                for filename in filenames
            )
            self.add_metric("build_total_size", build_size / (1024*1024), "MB", "frontend")
            
            # Analyze JS files
            js_files = []
            css_files = []
            
            for root, dirs, files in os.walk(build_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    
                    if file.endswith('.js'):
                        js_files.append((file, file_size))
                    elif file.endswith('.css'):
                        css_files.append((file, file_size))
            
            total_js_size = sum(size for _, size in js_files) / (1024*1024)
            total_css_size = sum(size for _, size in css_files) / (1024*1024)
            
            self.add_metric("build_js_size", total_js_size, "MB", "frontend")
            self.add_metric("build_css_size", total_css_size, "MB", "frontend")
            
            print(f"Build Total Size: {build_size / (1024*1024):.2f} MB")
            print(f"JavaScript Size: {total_js_size:.2f} MB")
            print(f"CSS Size: {total_css_size:.2f} MB")
            print(f"JS Files Count: {len(js_files)}")
            
        else:
            print("Build directory not found - run 'npm run build' first")
            
        # Check node_modules size
        if os.path.exists(node_modules_path):
            node_modules_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(node_modules_path)
                for filename in filenames
            )
            self.add_metric("node_modules_size", node_modules_size / (1024*1024*1024), "GB", "frontend")
            print(f"Node Modules Size: {node_modules_size / (1024*1024*1024):.2f} GB")
            
    def generate_report(self):
        """Generate comprehensive performance report"""
        print("\n" + "="*60)
        print("COMPREHENSIVE PERFORMANCE BENCHMARK REPORT")
        print("="*60)
        
        # Group metrics by category
        categories = {}
        for metric in self.metrics:
            if metric.category not in categories:
                categories[metric.category] = []
            categories[metric.category].append(metric)
        
        # Generate report for each category
        report_data = {
            "timestamp": time.time(),
            "categories": {},
            "summary": {}
        }
        
        for category, metrics in categories.items():
            print(f"\n{category.upper()} METRICS:")
            print("-" * 40)
            
            category_data = []
            for metric in metrics:
                print(f"{metric.name}: {metric.value:.4f} {metric.unit}")
                if metric.details:
                    for key, value in metric.details.items():
                        if key not in ['start_time', 'end_time']:
                            print(f"  {key}: {value}")
                
                category_data.append({
                    "name": metric.name,
                    "value": metric.value,
                    "unit": metric.unit,
                    "timestamp": metric.timestamp,
                    "details": metric.details
                })
            
            report_data["categories"][category] = category_data
            
        # Performance summary and recommendations
        print(f"\n{'PERFORMANCE SUMMARY'}")
        print("-" * 40)
        
        # Database performance summary
        db_metrics = categories.get("database", [])
        if db_metrics:
            avg_connection = next((m.value for m in db_metrics if m.name == "avg_db_connection_time"), 0)
            query_times = [m.value for m in db_metrics if m.name.startswith("query_")]
            
            if query_times:
                avg_query_time = statistics.mean(query_times)
                print(f"Database avg connection time: {avg_connection:.4f}s")
                print(f"Database avg query time: {avg_query_time:.4f}s")
                
                if avg_connection > 0.1:
                    print("  ⚠️  WARNING: Database connection time is high")
                if avg_query_time > 0.5:
                    print("  ⚠️  WARNING: Database query times are high")
        
        # API performance summary
        api_metrics = categories.get("api", [])
        if api_metrics:
            api_times = [m.value for m in api_metrics if not m.name.endswith("_error")]
            if api_times:
                avg_api_time = statistics.mean(api_times)
                print(f"API avg response time: {avg_api_time:.4f}s")
                
                if avg_api_time > 2.0:
                    print("  ⚠️  WARNING: API response times are high")
        
        # Frontend bundle analysis
        frontend_metrics = categories.get("frontend", [])
        if frontend_metrics:
            build_size = next((m.value for m in frontend_metrics if m.name == "build_total_size"), 0)
            node_modules_size = next((m.value for m in frontend_metrics if m.name == "node_modules_size"), 0)
            
            print(f"Frontend build size: {build_size:.2f} MB")
            print(f"Node modules size: {node_modules_size:.2f} GB")
            
            if build_size > 50:
                print("  ⚠️  WARNING: Build size is large")
            if node_modules_size > 2:
                print("  ⚠️  WARNING: Node modules size is large")
        
        # Save detailed report
        report_path = "/workspaces/Testing/docs/performance_benchmark_report.json"
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_path}")
        
        return report_data

def main():
    """Run comprehensive performance benchmarks"""
    benchmark = PerformanceBenchmark()
    
    print("Starting Comprehensive Performance Benchmark Suite...")
    print("This may take several minutes to complete.\n")
    
    # Run all benchmark tests
    benchmark.test_memory_usage()
    benchmark.test_database_performance() 
    benchmark.test_api_performance()
    benchmark.test_concurrent_load()
    benchmark.test_frontend_bundle_analysis()
    
    # Generate comprehensive report
    report = benchmark.generate_report()
    
    print("\n✅ Performance benchmark completed!")
    return report

if __name__ == "__main__":
    main()