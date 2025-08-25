#!/usr/bin/env python3
"""
Performance and Load Testing for External Connections
====================================================

Tests performance characteristics and load handling capabilities
of the application on both localhost and external IP addresses.

Features:
- Response time analysis
- Throughput testing  
- Concurrent connection handling
- Load testing under stress
- Network latency measurement
- Bandwidth utilization
- Resource consumption monitoring

Author: AI Model Validation Platform
Date: 2025-08-24
"""

import asyncio
import json
import logging
import time
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import threading

try:
    import requests
    import aiohttp
    import websocket
    import psutil
    import numpy as np
    import matplotlib.pyplot as plt
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError as e:
    print(f"Missing dependencies. Please install: {e}")
    print("Run: pip install requests aiohttp websocket-client psutil numpy matplotlib")
    exit(1)

@dataclass
class PerformanceMetric:
    """Performance metric data structure."""
    timestamp: datetime
    environment: str
    test_type: str
    metric_name: str
    value: float
    unit: str
    metadata: Dict[str, Any] = None

class PerformanceTestSuite:
    """Comprehensive performance testing suite."""
    
    def __init__(self):
        self.setup_logging()
        self.results = {
            'localhost': {},
            'external': {},
            'comparison': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Test configuration
        self.config = {
            'environments': {
                'localhost': {
                    'frontend_url': 'http://127.0.0.1:3000',
                    'backend_url': 'http://127.0.0.1:8000',
                    'websocket_url': 'ws://127.0.0.1:8000'
                },
                'external': {
                    'frontend_url': 'http://155.138.239.131:3000',
                    'backend_url': 'http://155.138.239.131:8000',
                    'websocket_url': 'ws://155.138.239.131:8000'
                }
            },
            'load_test': {
                'concurrent_users': [1, 5, 10, 25, 50, 100],
                'duration_seconds': 30,
                'ramp_up_time': 5
            },
            'stress_test': {
                'max_concurrent': 200,
                'duration_seconds': 60,
                'requests_per_second': [10, 50, 100, 200, 500]
            },
            'endpoints': [
                '/',
                '/health',
                '/api/health',
                '/api/projects',
                '/api/dashboard/stats'
            ]
        }
        
        self.metrics: List[PerformanceMetric] = []
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('performance_test.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def create_session(self) -> requests.Session:
        """Create optimized HTTP session."""
        session = requests.Session()
        
        # Configure retries
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
        
    def measure_response_time(self, url: str, session: requests.Session = None) -> Dict[str, Any]:
        """Measure detailed response time metrics."""
        if session is None:
            session = self.create_session()
            
        metrics = {
            'url': url,
            'success': False,
            'status_code': None,
            'response_time': None,
            'dns_lookup_time': 0,
            'tcp_connection_time': 0,
            'ssl_handshake_time': 0,
            'server_processing_time': 0,
            'content_transfer_time': 0,
            'total_time': 0,
            'content_length': 0,
            'error': None
        }
        
        try:
            start_time = time.time()
            response = session.get(url, timeout=30, verify=False, stream=True)
            
            # Basic timing
            total_time = time.time() - start_time
            
            # Get content
            content_start = time.time()
            content = response.content
            content_time = time.time() - content_start
            
            metrics.update({
                'success': True,
                'status_code': response.status_code,
                'response_time': total_time * 1000,  # ms
                'total_time': total_time * 1000,
                'content_transfer_time': content_time * 1000,
                'content_length': len(content)
            })
            
            # Calculate server processing time (approximate)
            metrics['server_processing_time'] = max(0, total_time - content_time) * 1000
            
        except Exception as e:
            metrics['error'] = str(e)
            metrics['response_time'] = (time.time() - start_time) * 1000
            
        return metrics
        
    def run_concurrent_test(self, url: str, concurrent_users: int, duration_seconds: int) -> Dict[str, Any]:
        """Run concurrent connection test."""
        results = {
            'concurrent_users': concurrent_users,
            'duration_seconds': duration_seconds,
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'requests_per_second': 0,
            'response_times': [],
            'error_rate': 0,
            'errors': []
        }
        
        session = self.create_session()
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        def make_request():
            """Make a single request."""
            try:
                response_time_data = self.measure_response_time(url, session)
                return response_time_data
            except Exception as e:
                return {'success': False, 'error': str(e)}
                
        # Run concurrent requests
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = []
            
            # Submit initial batch
            for _ in range(concurrent_users):
                future = executor.submit(make_request)
                futures.append(future)
                
            # Keep submitting requests until duration expires
            while time.time() < end_time:
                # Collect completed requests
                completed = []
                for future in futures:
                    if future.done():
                        try:
                            result = future.result()
                            results['total_requests'] += 1
                            
                            if result.get('success'):
                                results['successful_requests'] += 1
                                results['response_times'].append(result['response_time'])
                            else:
                                results['failed_requests'] += 1
                                if result.get('error'):
                                    results['errors'].append(result['error'])
                                    
                        except Exception as e:
                            results['failed_requests'] += 1
                            results['errors'].append(str(e))
                            
                        completed.append(future)
                        
                # Remove completed futures and submit new ones
                for future in completed:
                    futures.remove(future)
                    if time.time() < end_time:
                        new_future = executor.submit(make_request)
                        futures.append(new_future)
                        
                time.sleep(0.01)  # Small delay to prevent CPU spinning
                
            # Wait for remaining futures to complete
            for future in futures:
                try:
                    result = future.result(timeout=5)
                    results['total_requests'] += 1
                    
                    if result.get('success'):
                        results['successful_requests'] += 1
                        results['response_times'].append(result['response_time'])
                    else:
                        results['failed_requests'] += 1
                        if result.get('error'):
                            results['errors'].append(result['error'])
                            
                except Exception as e:
                    results['failed_requests'] += 1
                    results['errors'].append(str(e))
                    
        # Calculate final metrics
        actual_duration = time.time() - start_time
        results['actual_duration'] = actual_duration
        results['requests_per_second'] = results['total_requests'] / actual_duration
        results['error_rate'] = (results['failed_requests'] / max(results['total_requests'], 1)) * 100
        
        # Response time statistics
        if results['response_times']:
            response_times = results['response_times']
            results['response_time_stats'] = {
                'min': min(response_times),
                'max': max(response_times),
                'mean': statistics.mean(response_times),
                'median': statistics.median(response_times),
                'p95': np.percentile(response_times, 95),
                'p99': np.percentile(response_times, 99),
                'std_dev': statistics.stdev(response_times) if len(response_times) > 1 else 0
            }
        else:
            results['response_time_stats'] = None
            
        return results
        
    async def run_websocket_load_test(self, ws_url: str, concurrent_connections: int, duration_seconds: int) -> Dict[str, Any]:
        """Run WebSocket load test."""
        results = {
            'concurrent_connections': concurrent_connections,
            'duration_seconds': duration_seconds,
            'successful_connections': 0,
            'failed_connections': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'connection_times': [],
            'message_latencies': [],
            'errors': []
        }
        
        async def websocket_worker():
            """Single WebSocket worker."""
            try:
                # Create WebSocket connection
                start_time = time.time()
                
                ws = websocket.create_connection(
                    ws_url, 
                    timeout=10
                )
                
                connection_time = (time.time() - start_time) * 1000
                results['connection_times'].append(connection_time)
                results['successful_connections'] += 1
                
                # Send messages for duration
                end_time = time.time() + duration_seconds
                
                while time.time() < end_time:
                    try:
                        # Send ping
                        message_start = time.time()
                        ws.send(json.dumps({
                            'type': 'ping',
                            'timestamp': message_start
                        }))
                        results['messages_sent'] += 1
                        
                        # Try to receive response
                        try:
                            ws.settimeout(1.0)
                            response = ws.recv()
                            message_latency = (time.time() - message_start) * 1000
                            results['message_latencies'].append(message_latency)
                            results['messages_received'] += 1
                        except:
                            pass  # Timeout receiving message
                            
                        await asyncio.sleep(0.1)  # Rate limiting
                        
                    except Exception as e:
                        results['errors'].append(f"Message error: {e}")
                        break
                        
                ws.close()
                
            except Exception as e:
                results['failed_connections'] += 1
                results['errors'].append(f"Connection error: {e}")
                
        # Run concurrent WebSocket connections
        tasks = []
        for _ in range(concurrent_connections):
            task = asyncio.create_task(websocket_worker())
            tasks.append(task)
            await asyncio.sleep(0.01)  # Stagger connection attempts
            
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calculate statistics
        if results['connection_times']:
            results['connection_time_stats'] = {
                'min': min(results['connection_times']),
                'max': max(results['connection_times']),
                'mean': statistics.mean(results['connection_times']),
                'median': statistics.median(results['connection_times'])
            }
            
        if results['message_latencies']:
            results['message_latency_stats'] = {
                'min': min(results['message_latencies']),
                'max': max(results['message_latencies']),
                'mean': statistics.mean(results['message_latencies']),
                'median': statistics.median(results['message_latencies'])
            }
            
        return results
        
    def measure_bandwidth(self, url: str, duration_seconds: int = 10) -> Dict[str, Any]:
        """Measure bandwidth utilization."""
        results = {
            'duration_seconds': duration_seconds,
            'bytes_downloaded': 0,
            'requests_made': 0,
            'bandwidth_mbps': 0,
            'average_response_size': 0,
            'error': None
        }
        
        try:
            session = self.create_session()
            start_time = time.time()
            end_time = start_time + duration_seconds
            
            while time.time() < end_time:
                try:
                    response = session.get(url, timeout=5, verify=False)
                    content_length = len(response.content)
                    
                    results['bytes_downloaded'] += content_length
                    results['requests_made'] += 1
                    
                except Exception as e:
                    results['error'] = str(e)
                    break
                    
                time.sleep(0.1)  # Small delay between requests
                
            actual_duration = time.time() - start_time
            
            # Calculate bandwidth (Mbps)
            bytes_per_second = results['bytes_downloaded'] / actual_duration
            results['bandwidth_mbps'] = (bytes_per_second * 8) / (1024 * 1024)  # Convert to Mbps
            
            if results['requests_made'] > 0:
                results['average_response_size'] = results['bytes_downloaded'] / results['requests_made']
                
        except Exception as e:
            results['error'] = str(e)
            
        return results
        
    def analyze_network_latency(self, host: str) -> Dict[str, Any]:
        """Analyze network latency components."""
        import socket
        from urllib.parse import urlparse
        
        parsed_url = urlparse(f"http://{host}")
        hostname = parsed_url.hostname or host
        port = parsed_url.port or 80
        
        results = {
            'host': hostname,
            'port': port,
            'dns_resolution_time': None,
            'tcp_connection_time': None,
            'http_request_time': None,
            'total_latency': None,
            'error': None
        }
        
        try:
            # DNS Resolution Time
            dns_start = time.time()
            ip_address = socket.gethostbyname(hostname)
            dns_time = (time.time() - dns_start) * 1000
            results['dns_resolution_time'] = dns_time
            results['resolved_ip'] = ip_address
            
            # TCP Connection Time
            tcp_start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((ip_address, port))
            tcp_time = (time.time() - tcp_start) * 1000
            results['tcp_connection_time'] = tcp_time
            sock.close()
            
            # HTTP Request Time
            http_start = time.time()
            response = requests.get(f"http://{hostname}:{port}/health", timeout=10, verify=False)
            http_time = (time.time() - http_start) * 1000
            results['http_request_time'] = http_time
            
            # Total latency
            results['total_latency'] = dns_time + tcp_time + http_time
            
        except Exception as e:
            results['error'] = str(e)
            
        return results
        
    def run_performance_tests(self, environment: str) -> Dict[str, Any]:
        """Run comprehensive performance tests for environment."""
        config = self.config['environments'][environment]
        results = {}
        
        self.logger.info(f"\n🚀 Running performance tests for {environment.upper()}")
        
        # 1. Basic Response Time Tests
        self.logger.info("⏱️ Testing response times...")
        response_time_results = {}
        
        for endpoint in self.config['endpoints']:
            url = f"{config['backend_url']}{endpoint}"
            response_data = self.measure_response_time(url)
            response_time_results[endpoint] = response_data
            
            # Add metric
            if response_data['success']:
                self.metrics.append(PerformanceMetric(
                    timestamp=datetime.now(),
                    environment=environment,
                    test_type='response_time',
                    metric_name=f'endpoint_{endpoint.replace("/", "_")}',
                    value=response_data['response_time'],
                    unit='ms',
                    metadata={'endpoint': endpoint, 'status_code': response_data['status_code']}
                ))
                
        results['response_times'] = response_time_results
        
        # 2. Concurrent Load Tests
        self.logger.info("🔄 Running concurrent load tests...")
        load_test_results = {}
        
        health_url = f"{config['backend_url']}/health"
        
        for concurrent_users in self.config['load_test']['concurrent_users']:
            self.logger.info(f"  Testing {concurrent_users} concurrent users...")
            
            load_result = self.run_concurrent_test(
                health_url,
                concurrent_users,
                self.config['load_test']['duration_seconds']
            )
            
            load_test_results[f'{concurrent_users}_users'] = load_result
            
            # Add metrics
            if load_result['response_time_stats']:
                self.metrics.append(PerformanceMetric(
                    timestamp=datetime.now(),
                    environment=environment,
                    test_type='load_test',
                    metric_name=f'concurrent_{concurrent_users}_avg_response_time',
                    value=load_result['response_time_stats']['mean'],
                    unit='ms',
                    metadata={'concurrent_users': concurrent_users}
                ))
                
                self.metrics.append(PerformanceMetric(
                    timestamp=datetime.now(),
                    environment=environment,
                    test_type='load_test',
                    metric_name=f'concurrent_{concurrent_users}_rps',
                    value=load_result['requests_per_second'],
                    unit='rps',
                    metadata={'concurrent_users': concurrent_users}
                ))
                
        results['load_tests'] = load_test_results
        
        # 3. WebSocket Load Tests
        self.logger.info("🔌 Running WebSocket load tests...")
        
        try:
            ws_load_result = asyncio.run(self.run_websocket_load_test(
                config['websocket_url'],
                concurrent_connections=10,
                duration_seconds=15
            ))
            results['websocket_load'] = ws_load_result
            
            # Add metrics
            if ws_load_result['connection_time_stats']:
                self.metrics.append(PerformanceMetric(
                    timestamp=datetime.now(),
                    environment=environment,
                    test_type='websocket_load',
                    metric_name='websocket_connection_time',
                    value=ws_load_result['connection_time_stats']['mean'],
                    unit='ms'
                ))
                
        except Exception as e:
            self.logger.error(f"WebSocket load test failed: {e}")
            results['websocket_load'] = {'error': str(e)}
            
        # 4. Bandwidth Test
        self.logger.info("📊 Testing bandwidth utilization...")
        
        bandwidth_result = self.measure_bandwidth(health_url, duration_seconds=10)
        results['bandwidth'] = bandwidth_result
        
        if bandwidth_result['bandwidth_mbps'] > 0:
            self.metrics.append(PerformanceMetric(
                timestamp=datetime.now(),
                environment=environment,
                test_type='bandwidth',
                metric_name='bandwidth',
                value=bandwidth_result['bandwidth_mbps'],
                unit='mbps'
            ))
            
        # 5. Network Latency Analysis
        self.logger.info("🌐 Analyzing network latency...")
        
        from urllib.parse import urlparse
        hostname = urlparse(config['backend_url']).hostname
        latency_result = self.analyze_network_latency(hostname)
        results['network_latency'] = latency_result
        
        if latency_result['total_latency']:
            self.metrics.append(PerformanceMetric(
                timestamp=datetime.now(),
                environment=environment,
                test_type='network_latency',
                metric_name='total_latency',
                value=latency_result['total_latency'],
                unit='ms'
            ))
            
        return results
        
    def generate_performance_comparison(self) -> Dict[str, Any]:
        """Generate performance comparison between environments."""
        if 'localhost' not in self.results or 'external' not in self.results:
            return {'error': 'Both environments must be tested for comparison'}
            
        comparison = {
            'response_time_comparison': {},
            'load_test_comparison': {},
            'network_overhead': {},
            'recommendations': []
        }
        
        # Compare response times
        localhost_rt = self.results['localhost'].get('response_times', {})
        external_rt = self.results['external'].get('response_times', {})
        
        for endpoint in set(localhost_rt.keys()) & set(external_rt.keys()):
            local_time = localhost_rt[endpoint].get('response_time', 0)
            external_time = external_rt[endpoint].get('response_time', 0)
            
            if local_time > 0 and external_time > 0:
                overhead = external_time - local_time
                overhead_percentage = (overhead / local_time) * 100
                
                comparison['response_time_comparison'][endpoint] = {
                    'localhost_ms': local_time,
                    'external_ms': external_time,
                    'overhead_ms': overhead,
                    'overhead_percentage': overhead_percentage
                }
                
        # Compare load test results
        localhost_load = self.results['localhost'].get('load_tests', {})
        external_load = self.results['external'].get('load_tests', {})
        
        for test_key in set(localhost_load.keys()) & set(external_load.keys()):
            local_stats = localhost_load[test_key].get('response_time_stats')
            external_stats = external_load[test_key].get('response_time_stats')
            
            if local_stats and external_stats:
                comparison['load_test_comparison'][test_key] = {
                    'localhost_avg_ms': local_stats['mean'],
                    'external_avg_ms': external_stats['mean'],
                    'localhost_p95_ms': local_stats['p95'],
                    'external_p95_ms': external_stats['p95'],
                    'localhost_rps': localhost_load[test_key]['requests_per_second'],
                    'external_rps': external_load[test_key]['requests_per_second']
                }
                
        # Network overhead analysis
        localhost_latency = self.results['localhost'].get('network_latency', {})
        external_latency = self.results['external'].get('network_latency', {})
        
        if localhost_latency.get('total_latency') and external_latency.get('total_latency'):
            network_overhead = external_latency['total_latency'] - localhost_latency['total_latency']
            comparison['network_overhead'] = {
                'additional_latency_ms': network_overhead,
                'localhost_total_ms': localhost_latency['total_latency'],
                'external_total_ms': external_latency['total_latency']
            }
            
        # Generate recommendations
        recommendations = []
        
        # Response time recommendations
        avg_overhead = np.mean([
            comp.get('overhead_percentage', 0) 
            for comp in comparison['response_time_comparison'].values()
        ])
        
        if avg_overhead > 50:
            recommendations.append("⚠️ High network overhead detected. Consider CDN or edge caching.")
        elif avg_overhead > 20:
            recommendations.append("💡 Moderate network overhead. Monitor performance during peak usage.")
        else:
            recommendations.append("✅ Network overhead is acceptable for external access.")
            
        # Load test recommendations
        if comparison['load_test_comparison']:
            external_rps_values = [
                comp['external_rps'] 
                for comp in comparison['load_test_comparison'].values()
            ]
            max_external_rps = max(external_rps_values) if external_rps_values else 0
            
            if max_external_rps < 10:
                recommendations.append("🚨 Low external throughput. Check network capacity and server resources.")
            elif max_external_rps < 50:
                recommendations.append("⚠️ Limited external throughput. Consider scaling infrastructure.")
            else:
                recommendations.append("✅ Good external throughput capacity.")
                
        comparison['recommendations'] = recommendations
        
        return comparison
        
    def generate_performance_report(self) -> str:
        """Generate comprehensive performance report."""
        report_lines = [
            "=" * 80,
            "AI MODEL VALIDATION PLATFORM - PERFORMANCE TEST REPORT",
            "=" * 80,
            f"Generated: {self.results['timestamp']}",
            ""
        ]
        
        # Executive Summary
        report_lines.extend([
            "EXECUTIVE SUMMARY",
            "=" * 40,
            ""
        ])
        
        for env in ['localhost', 'external']:
            if env in self.results:
                env_results = self.results[env]
                report_lines.append(f"{env.upper()} ENVIRONMENT:")
                
                # Response time summary
                response_times = env_results.get('response_times', {})
                if response_times:
                    avg_response_time = np.mean([
                        rt.get('response_time', 0) 
                        for rt in response_times.values() 
                        if rt.get('success')
                    ])
                    report_lines.append(f"  Average Response Time: {avg_response_time:.2f}ms")
                    
                # Load test summary
                load_tests = env_results.get('load_tests', {})
                if load_tests:
                    max_rps = max([
                        lt.get('requests_per_second', 0) 
                        for lt in load_tests.values()
                    ])
                    report_lines.append(f"  Maximum Throughput: {max_rps:.2f} RPS")
                    
                # Bandwidth
                bandwidth = env_results.get('bandwidth', {})
                if bandwidth and bandwidth.get('bandwidth_mbps'):
                    report_lines.append(f"  Bandwidth: {bandwidth['bandwidth_mbps']:.2f} Mbps")
                    
                report_lines.append("")
                
        # Detailed Results
        report_lines.extend([
            "DETAILED PERFORMANCE RESULTS",
            "=" * 40,
            ""
        ])
        
        for env, env_results in self.results.items():
            if env in ['localhost', 'external']:
                report_lines.extend([
                    f"{env.upper()} ENVIRONMENT DETAILS:",
                    "-" * 30,
                    ""
                ])
                
                # Response Times
                if 'response_times' in env_results:
                    report_lines.append("Response Times:")
                    for endpoint, rt_data in env_results['response_times'].items():
                        if rt_data.get('success'):
                            report_lines.append(f"  {endpoint}: {rt_data['response_time']:.2f}ms (Status: {rt_data['status_code']})")
                        else:
                            report_lines.append(f"  {endpoint}: FAILED - {rt_data.get('error', 'Unknown error')}")
                    report_lines.append("")
                    
                # Load Test Results
                if 'load_tests' in env_results:
                    report_lines.append("Load Test Results:")
                    for test_name, lt_data in env_results['load_tests'].items():
                        users = test_name.replace('_users', '')
                        report_lines.append(f"  {users} concurrent users:")
                        report_lines.append(f"    Requests/sec: {lt_data['requests_per_second']:.2f}")
                        report_lines.append(f"    Success rate: {100 - lt_data['error_rate']:.1f}%")
                        
                        if lt_data.get('response_time_stats'):
                            stats = lt_data['response_time_stats']
                            report_lines.append(f"    Avg response: {stats['mean']:.2f}ms")
                            report_lines.append(f"    95th percentile: {stats['p95']:.2f}ms")
                            
                    report_lines.append("")
                    
                # Network Latency
                if 'network_latency' in env_results:
                    nl_data = env_results['network_latency']
                    if not nl_data.get('error'):
                        report_lines.extend([
                            "Network Latency Breakdown:",
                            f"  DNS Resolution: {nl_data.get('dns_resolution_time', 0):.2f}ms",
                            f"  TCP Connection: {nl_data.get('tcp_connection_time', 0):.2f}ms",
                            f"  HTTP Request: {nl_data.get('http_request_time', 0):.2f}ms",
                            f"  Total Latency: {nl_data.get('total_latency', 0):.2f}ms",
                            ""
                        ])
                        
        # Performance Comparison
        if 'comparison' in self.results:
            comparison = self.results['comparison']
            
            report_lines.extend([
                "PERFORMANCE COMPARISON",
                "=" * 40,
                ""
            ])
            
            # Response time comparison
            if 'response_time_comparison' in comparison:
                report_lines.append("Response Time Overhead:")
                for endpoint, comp_data in comparison['response_time_comparison'].items():
                    overhead_pct = comp_data['overhead_percentage']
                    overhead_ms = comp_data['overhead_ms']
                    report_lines.append(f"  {endpoint}: +{overhead_ms:.2f}ms ({overhead_pct:.1f}% overhead)")
                report_lines.append("")
                
            # Recommendations
            if 'recommendations' in comparison:
                report_lines.extend([
                    "RECOMMENDATIONS",
                    "-" * 20,
                    ""
                ])
                for rec in comparison['recommendations']:
                    report_lines.append(f"  {rec}")
                report_lines.append("")
                
        report_lines.extend([
            "=" * 80,
            "End of Performance Report",
            "=" * 80
        ])
        
        return "\n".join(report_lines)
        
    async def run_all_performance_tests(self):
        """Run all performance tests."""
        self.logger.info("🚀 Starting Performance Test Suite")
        self.logger.info("=" * 80)
        
        # Test localhost
        try:
            self.results['localhost'] = self.run_performance_tests('localhost')
        except Exception as e:
            self.logger.error(f"Localhost performance tests failed: {e}")
            self.results['localhost'] = {'error': str(e)}
            
        # Test external IP
        try:
            self.results['external'] = self.run_performance_tests('external')
        except Exception as e:
            self.logger.error(f"External performance tests failed: {e}")
            self.results['external'] = {'error': str(e)}
            
        # Generate comparison
        self.results['comparison'] = self.generate_performance_comparison()
        
        # Generate and save report
        report = self.generate_performance_report()
        
        # Save detailed results
        with open('performance_test_results.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
            
        # Save human-readable report
        with open('performance_test_report.txt', 'w') as f:
            f.write(report)
            
        # Save metrics
        metrics_data = [asdict(metric) for metric in self.metrics]
        with open('performance_metrics.json', 'w') as f:
            json.dump(metrics_data, f, indent=2, default=str)
            
        self.logger.info("\n" + report)
        
        return self.results


async def main():
    """Main performance test execution function."""
    suite = PerformanceTestSuite()
    results = await suite.run_all_performance_tests()
    
    # Check for critical performance issues
    critical_issues = 0
    
    for env in ['localhost', 'external']:
        if env in results:
            env_results = results[env]
            
            # Check if any services are completely failing
            response_times = env_results.get('response_times', {})
            failed_endpoints = [
                endpoint for endpoint, data in response_times.items()
                if not data.get('success')
            ]
            
            if failed_endpoints:
                critical_issues += len(failed_endpoints)
                print(f"❌ {len(failed_endpoints)} endpoints failed in {env}")
                
            # Check for extremely poor performance
            load_tests = env_results.get('load_tests', {})
            for test_name, test_data in load_tests.items():
                if test_data.get('error_rate', 0) > 50:
                    critical_issues += 1
                    print(f"❌ High error rate in {env} {test_name}: {test_data['error_rate']:.1f}%")
                    
    if critical_issues > 0:
        print(f"\n❌ {critical_issues} critical performance issues found")
        exit(1)
    else:
        print("\n✅ Performance tests completed successfully")
        exit(0)


if __name__ == "__main__":
    asyncio.run(main())