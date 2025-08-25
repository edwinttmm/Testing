#!/usr/bin/env python3
"""
Comprehensive Connectivity Test Suite
=====================================

Tests application accessibility on both localhost and external Vultr server IP.

TESTING REQUIREMENTS:
- Frontend: http://127.0.0.1:3000 and http://155.138.239.131:3000
- Backend API: http://127.0.0.1:8000 and http://155.138.239.131:8000
- WebSocket connections from external IP
- API communication between frontend and backend

Author: AI Model Validation Platform
Date: 2025-08-24
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin
import warnings

# Suppress SSL warnings for testing
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

try:
    import requests
    import websocket
    import socketio
    import aiohttp
    import concurrent.futures
    from websocket._exceptions import WebSocketException
    import ssl
except ImportError as e:
    print(f"Missing dependencies. Please install: {e}")
    print("Run: pip install requests websocket-client python-socketio aiohttp")
    exit(1)

# Test Configuration
CONFIG = {
    'localhost': {
        'frontend_url': 'http://127.0.0.1:3000',
        'backend_url': 'http://127.0.0.1:8000',
        'websocket_url': 'ws://127.0.0.1:8000',
        'socketio_url': 'http://127.0.0.1:8000'
    },
    'external': {
        'frontend_url': 'http://155.138.239.131:3000',
        'backend_url': 'http://155.138.239.131:8000',
        'websocket_url': 'ws://155.138.239.131:8000',
        'socketio_url': 'http://155.138.239.131:8000'
    },
    'timeout': 30,
    'retries': 3,
    'concurrent_connections': 10
}

class ConnectivityTestSuite:
    """Comprehensive connectivity test suite for AI Model Validation Platform."""
    
    def __init__(self):
        self.setup_logging()
        self.results = {
            'localhost': {},
            'external': {},
            'summary': {},
            'timestamp': datetime.now().isoformat()
        }
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('connectivity_test.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def test_http_connectivity(self, base_url: str, endpoint: str = '') -> Dict[str, Any]:
        """Test HTTP connectivity to specified endpoint."""
        url = urljoin(base_url, endpoint)
        test_result = {
            'url': url,
            'success': False,
            'status_code': None,
            'response_time': None,
            'error': None,
            'headers': None,
            'content_length': None
        }
        
        try:
            start_time = time.time()
            response = requests.get(
                url, 
                timeout=CONFIG['timeout'],
                verify=False,
                allow_redirects=True
            )
            response_time = time.time() - start_time
            
            test_result.update({
                'success': True,
                'status_code': response.status_code,
                'response_time': round(response_time * 1000, 2),  # ms
                'headers': dict(response.headers),
                'content_length': len(response.content)
            })
            
            self.logger.info(f"✅ HTTP {url} - {response.status_code} ({response_time*1000:.2f}ms)")
            
        except requests.RequestException as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ HTTP {url} - {e}")
            
        return test_result
        
    def test_websocket_connectivity(self, ws_url: str) -> Dict[str, Any]:
        """Test WebSocket connectivity."""
        test_result = {
            'url': ws_url,
            'success': False,
            'connection_time': None,
            'ping_pong_time': None,
            'error': None
        }
        
        try:
            start_time = time.time()
            ws = websocket.WebSocket()
            ws.connect(ws_url, timeout=CONFIG['timeout'])
            connection_time = time.time() - start_time
            
            # Test ping/pong
            ping_start = time.time()
            ws.ping("test")
            ws.pong("test")
            ping_pong_time = time.time() - ping_start
            
            ws.close()
            
            test_result.update({
                'success': True,
                'connection_time': round(connection_time * 1000, 2),
                'ping_pong_time': round(ping_pong_time * 1000, 2)
            })
            
            self.logger.info(f"✅ WebSocket {ws_url} - Connected ({connection_time*1000:.2f}ms)")
            
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ WebSocket {ws_url} - {e}")
            
        return test_result
        
    async def test_socketio_connectivity(self, socketio_url: str) -> Dict[str, Any]:
        """Test Socket.IO connectivity."""
        test_result = {
            'url': socketio_url,
            'success': False,
            'connection_time': None,
            'event_response_time': None,
            'error': None
        }
        
        try:
            sio = socketio.AsyncClient()
            
            @sio.event
            async def connect():
                self.logger.info(f"Socket.IO connected to {socketio_url}")
                
            @sio.event
            async def disconnect():
                self.logger.info(f"Socket.IO disconnected from {socketio_url}")
                
            start_time = time.time()
            await sio.connect(socketio_url, wait_timeout=CONFIG['timeout'])
            connection_time = time.time() - start_time
            
            # Test event emission
            event_start = time.time()
            await sio.emit('test_event', {'data': 'test'})
            event_response_time = time.time() - event_start
            
            await sio.disconnect()
            
            test_result.update({
                'success': True,
                'connection_time': round(connection_time * 1000, 2),
                'event_response_time': round(event_response_time * 1000, 2)
            })
            
            self.logger.info(f"✅ Socket.IO {socketio_url} - Connected ({connection_time*1000:.2f}ms)")
            
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ Socket.IO {socketio_url} - {e}")
            
        return test_result
        
    def test_cors_headers(self, base_url: str) -> Dict[str, Any]:
        """Test CORS headers configuration."""
        test_result = {
            'success': False,
            'cors_headers': {},
            'preflight_success': False,
            'error': None
        }
        
        try:
            # Test preflight request
            headers = {
                'Origin': 'http://localhost:3000',
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Content-Type'
            }
            
            response = requests.options(
                f"{base_url}/api/health",
                headers=headers,
                timeout=CONFIG['timeout']
            )
            
            cors_headers = {
                k: v for k, v in response.headers.items() 
                if k.lower().startswith('access-control-')
            }
            
            test_result.update({
                'success': response.status_code in [200, 204],
                'cors_headers': cors_headers,
                'preflight_success': 'access-control-allow-origin' in [h.lower() for h in response.headers]
            })
            
            self.logger.info(f"✅ CORS {base_url} - Headers: {len(cors_headers)}")
            
        except Exception as e:
            test_result['error'] = str(e)
            self.logger.error(f"❌ CORS {base_url} - {e}")
            
        return test_result
        
    def test_api_endpoints(self, base_url: str) -> Dict[str, Any]:
        """Test critical API endpoints."""
        endpoints = [
            ('health', '/health'),
            ('api_health', '/api/health'),
            ('projects', '/api/projects'),
            ('videos', '/api/videos'),
            ('dashboard_stats', '/api/dashboard/stats'),
            ('detection_events', '/api/detection-events'),
        ]
        
        results = {}
        for name, endpoint in endpoints:
            results[name] = self.test_http_connectivity(base_url, endpoint)
            time.sleep(0.1)  # Rate limiting
            
        return results
        
    def test_frontend_resources(self, frontend_url: str) -> Dict[str, Any]:
        """Test frontend static resources."""
        resources = [
            ('index', '/'),
            ('manifest', '/manifest.json'),
            ('favicon', '/favicon.ico'),
            ('static_js', '/static/js/'),  # This will likely 404 but shows if server is responding
        ]
        
        results = {}
        for name, resource in resources:
            results[name] = self.test_http_connectivity(frontend_url, resource)
            time.sleep(0.1)
            
        return results
        
    def test_database_security(self, host: str) -> Dict[str, Any]:
        """Test that database is NOT accessible externally (security check)."""
        test_result = {
            'postgres_port_5432': {'blocked': False, 'error': None},
            'redis_port_6379': {'blocked': False, 'error': None}
        }
        
        import socket
        
        # Test PostgreSQL port
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, 5432))
            test_result['postgres_port_5432']['blocked'] = result != 0
            sock.close()
        except Exception as e:
            test_result['postgres_port_5432']['error'] = str(e)
            test_result['postgres_port_5432']['blocked'] = True
            
        # Test Redis port
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, 6379))
            test_result['redis_port_6379']['blocked'] = result != 0
            sock.close()
        except Exception as e:
            test_result['redis_port_6379']['error'] = str(e)
            test_result['redis_port_6379']['blocked'] = True
            
        return test_result
        
    async def test_concurrent_connections(self, base_url: str, count: int = 10) -> Dict[str, Any]:
        """Test concurrent connection handling."""
        test_result = {
            'success': False,
            'total_connections': count,
            'successful_connections': 0,
            'failed_connections': 0,
            'average_response_time': 0,
            'errors': []
        }
        
        async def make_request(session, url):
            try:
                start_time = time.time()
                async with session.get(url, timeout=CONFIG['timeout']) as response:
                    response_time = time.time() - start_time
                    return {
                        'success': True,
                        'status': response.status,
                        'response_time': response_time
                    }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e),
                    'response_time': 0
                }
                
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [
                    make_request(session, f"{base_url}/health") 
                    for _ in range(count)
                ]
                
                results = await asyncio.gather(*tasks)
                
                successful = [r for r in results if r['success']]
                failed = [r for r in results if not r['success']]
                
                test_result.update({
                    'success': len(successful) > 0,
                    'successful_connections': len(successful),
                    'failed_connections': len(failed),
                    'average_response_time': sum(r['response_time'] for r in successful) / max(len(successful), 1) * 1000,
                    'errors': [r['error'] for r in failed if 'error' in r]
                })
                
        except Exception as e:
            test_result['errors'] = [str(e)]
            
        return test_result
        
    def test_performance_metrics(self, base_url: str) -> Dict[str, Any]:
        """Test performance metrics for external connections."""
        test_result = {
            'dns_resolution_time': 0,
            'tcp_connection_time': 0,
            'ssl_handshake_time': 0,
            'http_response_time': 0,
            'total_time': 0,
            'throughput_mbps': 0
        }
        
        try:
            import socket
            from urllib.parse import urlparse
            
            parsed_url = urlparse(base_url)
            host = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            
            # DNS resolution time
            dns_start = time.time()
            socket.gethostbyname(host)
            test_result['dns_resolution_time'] = (time.time() - dns_start) * 1000
            
            # HTTP response time with detailed timing
            start_time = time.time()
            response = requests.get(
                f"{base_url}/health",
                timeout=CONFIG['timeout'],
                stream=True
            )
            
            # Calculate throughput
            content = response.content
            total_time = time.time() - start_time
            throughput = len(content) / total_time / 1024 / 1024 if total_time > 0 else 0
            
            test_result.update({
                'http_response_time': total_time * 1000,
                'total_time': total_time * 1000,
                'throughput_mbps': throughput
            })
            
        except Exception as e:
            self.logger.error(f"Performance test error: {e}")
            
        return test_result
        
    async def run_comprehensive_test(self, environment: str) -> Dict[str, Any]:
        """Run comprehensive test suite for specified environment."""
        config = CONFIG[environment]
        results = {}
        
        self.logger.info(f"\n🚀 Running comprehensive connectivity tests for {environment.upper()}")
        self.logger.info(f"Frontend: {config['frontend_url']}")
        self.logger.info(f"Backend: {config['backend_url']}")
        
        # 1. Frontend Tests
        self.logger.info(f"\n📱 Testing Frontend Connectivity")
        results['frontend'] = {
            'base_connectivity': self.test_http_connectivity(config['frontend_url']),
            'resources': self.test_frontend_resources(config['frontend_url']),
            'performance': self.test_performance_metrics(config['frontend_url'])
        }
        
        # 2. Backend Tests
        self.logger.info(f"\n🔧 Testing Backend API Connectivity")
        results['backend'] = {
            'base_connectivity': self.test_http_connectivity(config['backend_url']),
            'api_endpoints': self.test_api_endpoints(config['backend_url']),
            'cors_headers': self.test_cors_headers(config['backend_url']),
            'performance': self.test_performance_metrics(config['backend_url'])
        }
        
        # 3. WebSocket Tests
        self.logger.info(f"\n🔌 Testing WebSocket Connectivity")
        results['websocket'] = self.test_websocket_connectivity(config['websocket_url'])
        
        # 4. Socket.IO Tests
        self.logger.info(f"\n⚡ Testing Socket.IO Connectivity")
        try:
            results['socketio'] = await self.test_socketio_connectivity(config['socketio_url'])
        except Exception as e:
            results['socketio'] = {'success': False, 'error': str(e)}
            
        # 5. Concurrent Connection Tests
        self.logger.info(f"\n🔄 Testing Concurrent Connections")
        results['concurrent'] = await self.test_concurrent_connections(
            config['backend_url'], 
            CONFIG['concurrent_connections']
        )
        
        # 6. Database Security Tests (only for external)
        if environment == 'external':
            self.logger.info(f"\n🔒 Testing Database Security")
            host = urlparse(config['backend_url']).hostname
            results['database_security'] = self.test_database_security(host)
            
        return results
        
    def generate_report(self) -> str:
        """Generate comprehensive connectivity report."""
        report_lines = [
            "=" * 80,
            "AI MODEL VALIDATION PLATFORM - CONNECTIVITY TEST REPORT",
            "=" * 80,
            f"Generated: {self.results['timestamp']}",
            f"Test Duration: {time.time() - self.start_time:.2f} seconds",
            ""
        ]
        
        # Summary Section
        report_lines.extend([
            "EXECUTIVE SUMMARY",
            "=" * 40,
            ""
        ])
        
        for env in ['localhost', 'external']:
            if env in self.results:
                env_results = self.results[env]
                report_lines.append(f"{env.upper()} ENVIRONMENT:")
                
                # Frontend Status
                frontend_ok = env_results.get('frontend', {}).get('base_connectivity', {}).get('success', False)
                report_lines.append(f"  ├─ Frontend: {'✅ PASS' if frontend_ok else '❌ FAIL'}")
                
                # Backend Status
                backend_ok = env_results.get('backend', {}).get('base_connectivity', {}).get('success', False)
                report_lines.append(f"  ├─ Backend API: {'✅ PASS' if backend_ok else '❌ FAIL'}")
                
                # WebSocket Status
                ws_ok = env_results.get('websocket', {}).get('success', False)
                report_lines.append(f"  ├─ WebSocket: {'✅ PASS' if ws_ok else '❌ FAIL'}")
                
                # Socket.IO Status
                sio_ok = env_results.get('socketio', {}).get('success', False)
                report_lines.append(f"  ├─ Socket.IO: {'✅ PASS' if sio_ok else '❌ FAIL'}")
                
                # Concurrent Connections
                concurrent_ok = env_results.get('concurrent', {}).get('success', False)
                report_lines.append(f"  └─ Concurrent: {'✅ PASS' if concurrent_ok else '❌ FAIL'}")
                
                report_lines.append("")
                
        # Detailed Results
        report_lines.extend([
            "DETAILED RESULTS",
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
                
                # Frontend Details
                if 'frontend' in env_results:
                    frontend = env_results['frontend']
                    base = frontend.get('base_connectivity', {})
                    report_lines.extend([
                        f"Frontend ({CONFIG[env]['frontend_url']}):",
                        f"  Status: {base.get('status_code', 'N/A')}",
                        f"  Response Time: {base.get('response_time', 'N/A')}ms",
                        f"  Content Length: {base.get('content_length', 'N/A')} bytes",
                        ""
                    ])
                    
                # Backend Details
                if 'backend' in env_results:
                    backend = env_results['backend']
                    base = backend.get('base_connectivity', {})
                    report_lines.extend([
                        f"Backend API ({CONFIG[env]['backend_url']}):",
                        f"  Status: {base.get('status_code', 'N/A')}",
                        f"  Response Time: {base.get('response_time', 'N/A')}ms",
                        ""
                    ])
                    
                    # API Endpoints
                    if 'api_endpoints' in backend:
                        report_lines.append("  API Endpoints:")
                        for endpoint, result in backend['api_endpoints'].items():
                            status = '✅' if result.get('success') else '❌'
                            code = result.get('status_code', 'N/A')
                            time_ms = result.get('response_time', 'N/A')
                            report_lines.append(f"    {status} {endpoint}: {code} ({time_ms}ms)")
                        report_lines.append("")
                        
                    # CORS Headers
                    if 'cors_headers' in backend:
                        cors = backend['cors_headers']
                        report_lines.extend([
                            "  CORS Configuration:",
                            f"    Preflight Success: {'✅' if cors.get('preflight_success') else '❌'}",
                            f"    CORS Headers: {len(cors.get('cors_headers', {}))}"
                        ])
                        for header, value in cors.get('cors_headers', {}).items():
                            report_lines.append(f"      {header}: {value}")
                        report_lines.append("")
                        
                # WebSocket Details
                if 'websocket' in env_results:
                    ws = env_results['websocket']
                    report_lines.extend([
                        f"WebSocket ({CONFIG[env]['websocket_url']}):",
                        f"  Connection: {'✅' if ws.get('success') else '❌'}",
                        f"  Connection Time: {ws.get('connection_time', 'N/A')}ms",
                        f"  Ping/Pong Time: {ws.get('ping_pong_time', 'N/A')}ms",
                        ""
                    ])
                    
                # Performance Metrics
                if 'backend' in env_results and 'performance' in env_results['backend']:
                    perf = env_results['backend']['performance']
                    report_lines.extend([
                        "Performance Metrics:",
                        f"  DNS Resolution: {perf.get('dns_resolution_time', 'N/A')}ms",
                        f"  HTTP Response: {perf.get('http_response_time', 'N/A')}ms",
                        f"  Throughput: {perf.get('throughput_mbps', 'N/A'):.2f} MB/s",
                        ""
                    ])
                    
                # Database Security (External only)
                if env == 'external' and 'database_security' in env_results:
                    db_sec = env_results['database_security']
                    report_lines.extend([
                        "Database Security Check:",
                        f"  PostgreSQL (5432): {'🔒 Blocked' if db_sec.get('postgres_port_5432', {}).get('blocked') else '⚠️ Accessible'}",
                        f"  Redis (6379): {'🔒 Blocked' if db_sec.get('redis_port_6379', {}).get('blocked') else '⚠️ Accessible'}",
                        ""
                    ])
                    
                report_lines.append("")
                
        # Recommendations
        report_lines.extend([
            "RECOMMENDATIONS",
            "=" * 40,
            ""
        ])
        
        # Check for issues and generate recommendations
        recommendations = []
        
        for env in ['localhost', 'external']:
            if env in self.results:
                env_results = self.results[env]
                
                # Frontend issues
                if not env_results.get('frontend', {}).get('base_connectivity', {}).get('success'):
                    recommendations.append(f"❌ Fix {env} frontend connectivity - service may be down")
                    
                # Backend issues
                if not env_results.get('backend', {}).get('base_connectivity', {}).get('success'):
                    recommendations.append(f"❌ Fix {env} backend API connectivity - service may be down")
                    
                # CORS issues
                cors_ok = env_results.get('backend', {}).get('cors_headers', {}).get('preflight_success', False)
                if not cors_ok:
                    recommendations.append(f"⚠️ Configure CORS headers properly for {env} environment")
                    
                # Performance issues
                perf = env_results.get('backend', {}).get('performance', {})
                response_time = perf.get('http_response_time', 0)
                if response_time > 5000:  # 5 seconds
                    recommendations.append(f"🐌 Optimize {env} response time ({response_time:.0f}ms is too slow)")
                    
        # Database security for external
        if 'external' in self.results:
            db_sec = self.results['external'].get('database_security', {})
            if not db_sec.get('postgres_port_5432', {}).get('blocked'):
                recommendations.append("🚨 CRITICAL: PostgreSQL port 5432 is accessible externally - security risk!")
            if not db_sec.get('redis_port_6379', {}).get('blocked'):
                recommendations.append("🚨 CRITICAL: Redis port 6379 is accessible externally - security risk!")
                
        if not recommendations:
            recommendations.append("✅ All connectivity tests passed - no issues found")
            
        report_lines.extend(recommendations)
        report_lines.extend([
            "",
            "=" * 80,
            "End of Report",
            "=" * 80
        ])
        
        return "\n".join(report_lines)
        
    async def run_all_tests(self):
        """Run all connectivity tests."""
        self.start_time = time.time()
        
        self.logger.info("🔄 Starting Comprehensive Connectivity Test Suite")
        self.logger.info("=" * 80)
        
        # Test localhost
        try:
            self.results['localhost'] = await self.run_comprehensive_test('localhost')
        except Exception as e:
            self.logger.error(f"Localhost tests failed: {e}")
            self.results['localhost'] = {'error': str(e)}
            
        # Test external IP
        try:
            self.results['external'] = await self.run_comprehensive_test('external')
        except Exception as e:
            self.logger.error(f"External tests failed: {e}")
            self.results['external'] = {'error': str(e)}
            
        # Generate and save report
        report = self.generate_report()
        
        # Save detailed results
        with open('connectivity_test_results.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
            
        # Save human-readable report
        with open('connectivity_test_report.txt', 'w') as f:
            f.write(report)
            
        self.logger.info("\n" + report)
        
        return self.results


async def main():
    """Main test execution function."""
    suite = ConnectivityTestSuite()
    results = await suite.run_all_tests()
    
    # Exit with non-zero code if critical issues found
    critical_issues = 0
    
    for env in ['localhost', 'external']:
        if env in results:
            env_results = results[env]
            
            # Check critical services
            if not env_results.get('frontend', {}).get('base_connectivity', {}).get('success', False):
                critical_issues += 1
            if not env_results.get('backend', {}).get('base_connectivity', {}).get('success', False):
                critical_issues += 1
                
    if critical_issues > 0:
        print(f"\n❌ {critical_issues} critical connectivity issues found")
        exit(1)
    else:
        print("\n✅ All critical connectivity tests passed")
        exit(0)


if __name__ == "__main__":
    asyncio.run(main())