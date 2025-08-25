#!/usr/bin/env python3
"""
Quick Connectivity Test - Minimal Dependencies
==============================================

A lightweight connectivity test that works with standard library modules only.
Tests basic connectivity to both localhost and external IP without external dependencies.

Author: AI Model Validation Platform
Date: 2025-08-24
"""

import sys
import json
import time
import socket
import http.client
from urllib.parse import urlparse
from datetime import datetime
import logging

class QuickConnectivityTest:
    """Quick connectivity test with minimal dependencies."""
    
    def __init__(self):
        self.setup_logging()
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'localhost': {},
            'external': {},
            'summary': {}
        }
        
        self.environments = {
            'localhost': {
                'frontend_host': '127.0.0.1',
                'frontend_port': 3000,
                'backend_host': '127.0.0.1', 
                'backend_port': 8000
            },
            'external': {
                'frontend_host': '155.138.239.131',
                'frontend_port': 3000,
                'backend_host': '155.138.239.131',
                'backend_port': 8000
            }
        }
        
    def setup_logging(self):
        """Setup basic logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def test_tcp_connection(self, host, port, timeout=10):
        """Test TCP connection."""
        result = {
            'host': host,
            'port': port,
            'success': False,
            'connection_time': None,
            'error': None
        }
        
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            sock.connect((host, port))
            connection_time = (time.time() - start_time) * 1000
            
            sock.close()
            
            result.update({
                'success': True,
                'connection_time': round(connection_time, 2)
            })
            
        except Exception as e:
            result['error'] = str(e)
            
        return result
        
    def test_http_request(self, host, port, path='/', timeout=10):
        """Test HTTP request."""
        result = {
            'url': f'http://{host}:{port}{path}',
            'success': False,
            'status_code': None,
            'response_time': None,
            'error': None
        }
        
        try:
            start_time = time.time()
            
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
            conn.request('GET', path)
            response = conn.getresponse()
            
            response_time = (time.time() - start_time) * 1000
            
            result.update({
                'success': response.status < 400,
                'status_code': response.status,
                'response_time': round(response_time, 2)
            })
            
            conn.close()
            
        except Exception as e:
            result['error'] = str(e)
            
        return result
        
    def test_dns_resolution(self, hostname):
        """Test DNS resolution."""
        result = {
            'hostname': hostname,
            'success': False,
            'ip_address': None,
            'resolution_time': None,
            'error': None
        }
        
        try:
            start_time = time.time()
            ip_address = socket.gethostbyname(hostname)
            resolution_time = (time.time() - start_time) * 1000
            
            result.update({
                'success': True,
                'ip_address': ip_address,
                'resolution_time': round(resolution_time, 2)
            })
            
        except Exception as e:
            result['error'] = str(e)
            
        return result
        
    def test_environment(self, env_name):
        """Test connectivity for specific environment."""
        env_config = self.environments[env_name]
        results = {}
        
        self.logger.info(f"Testing {env_name} environment...")
        
        # Test DNS resolution
        if env_name == 'external':
            dns_result = self.test_dns_resolution(env_config['frontend_host'])
            results['dns_resolution'] = dns_result
            self.logger.info(f"DNS Resolution: {'✅' if dns_result['success'] else '❌'}")
            
        # Test frontend TCP connection
        frontend_tcp = self.test_tcp_connection(
            env_config['frontend_host'], 
            env_config['frontend_port']
        )
        results['frontend_tcp'] = frontend_tcp
        self.logger.info(f"Frontend TCP: {'✅' if frontend_tcp['success'] else '❌'}")
        
        # Test backend TCP connection
        backend_tcp = self.test_tcp_connection(
            env_config['backend_host'],
            env_config['backend_port']
        )
        results['backend_tcp'] = backend_tcp
        self.logger.info(f"Backend TCP: {'✅' if backend_tcp['success'] else '❌'}")
        
        # Test frontend HTTP
        if frontend_tcp['success']:
            frontend_http = self.test_http_request(
                env_config['frontend_host'],
                env_config['frontend_port'],
                '/'
            )
            results['frontend_http'] = frontend_http
            self.logger.info(f"Frontend HTTP: {'✅' if frontend_http['success'] else '❌'}")
            
        # Test backend HTTP (health endpoint)
        if backend_tcp['success']:
            backend_health = self.test_http_request(
                env_config['backend_host'],
                env_config['backend_port'],
                '/health'
            )
            results['backend_health'] = backend_health
            self.logger.info(f"Backend Health: {'✅' if backend_health['success'] else '❌'}")
            
            # Test backend API
            backend_api = self.test_http_request(
                env_config['backend_host'],
                env_config['backend_port'],
                '/api/health'
            )
            results['backend_api'] = backend_api  
            self.logger.info(f"Backend API: {'✅' if backend_api['success'] else '❌'}")
            
        # Test database security (ports should be blocked externally)
        if env_name == 'external':
            postgres_blocked = self.test_tcp_connection(
                env_config['backend_host'], 5432, timeout=5
            )
            redis_blocked = self.test_tcp_connection(
                env_config['backend_host'], 6379, timeout=5
            )
            
            results['database_security'] = {
                'postgres_5432_blocked': not postgres_blocked['success'],
                'redis_6379_blocked': not redis_blocked['success']
            }
            
            postgres_status = '🔒' if not postgres_blocked['success'] else '⚠️ EXPOSED'
            redis_status = '🔒' if not redis_blocked['success'] else '⚠️ EXPOSED'
            self.logger.info(f"PostgreSQL Security: {postgres_status}")
            self.logger.info(f"Redis Security: {redis_status}")
            
        return results
        
    def analyze_results(self):
        """Analyze all test results."""
        summary = {
            'localhost_healthy': True,
            'external_healthy': True,
            'security_issues': [],
            'connectivity_issues': [],
            'recommendations': []
        }
        
        # Check localhost
        localhost_results = self.results.get('localhost', {})
        if not localhost_results.get('frontend_http', {}).get('success'):
            summary['localhost_healthy'] = False
            summary['connectivity_issues'].append('Localhost frontend not accessible')
            
        if not localhost_results.get('backend_health', {}).get('success'):
            summary['localhost_healthy'] = False
            summary['connectivity_issues'].append('Localhost backend not accessible')
            
        # Check external
        external_results = self.results.get('external', {})
        if not external_results.get('frontend_http', {}).get('success'):
            summary['external_healthy'] = False
            summary['connectivity_issues'].append('External frontend not accessible')
            
        if not external_results.get('backend_health', {}).get('success'):
            summary['external_healthy'] = False
            summary['connectivity_issues'].append('External backend not accessible')
            
        # Check database security
        db_security = external_results.get('database_security', {})
        if not db_security.get('postgres_5432_blocked', True):
            summary['security_issues'].append('PostgreSQL port 5432 is exposed externally')
            
        if not db_security.get('redis_6379_blocked', True):
            summary['security_issues'].append('Redis port 6379 is exposed externally')
            
        # Generate recommendations
        recommendations = []
        
        if summary['localhost_healthy'] and summary['external_healthy']:
            recommendations.append('✅ Both environments are accessible - connectivity verified')
        else:
            if not summary['localhost_healthy']:
                recommendations.append('❌ Fix localhost connectivity issues first')
            if not summary['external_healthy']:
                recommendations.append('❌ Fix external connectivity issues')
                
        if summary['security_issues']:
            recommendations.append('🚨 CRITICAL: Fix database security issues immediately')
        else:
            recommendations.append('🔒 Database security is properly configured')
            
        if not summary['connectivity_issues'] and not summary['security_issues']:
            recommendations.append('🚀 System ready for deployment')
            
        summary['recommendations'] = recommendations
        
        return summary
        
    def generate_report(self):
        """Generate human-readable report."""
        report_lines = [
            "=" * 60,
            "AI MODEL VALIDATION PLATFORM - QUICK CONNECTIVITY TEST",
            "=" * 60,
            f"Test Time: {self.results['timestamp']}",
            ""
        ]
        
        # Environment Results
        for env_name in ['localhost', 'external']:
            if env_name in self.results:
                results = self.results[env_name]
                report_lines.extend([
                    f"{env_name.upper()} ENVIRONMENT:",
                    "-" * 30
                ])
                
                # DNS (external only)
                if 'dns_resolution' in results:
                    dns = results['dns_resolution']
                    status = '✅' if dns['success'] else '❌'
                    ip = dns.get('ip_address', 'N/A')
                    time_ms = dns.get('resolution_time', 'N/A')
                    report_lines.append(f"DNS Resolution: {status} {ip} ({time_ms}ms)")
                    
                # TCP Connections
                for service in ['frontend', 'backend']:
                    tcp_key = f'{service}_tcp'
                    if tcp_key in results:
                        tcp = results[tcp_key]
                        status = '✅' if tcp['success'] else '❌'
                        time_ms = tcp.get('connection_time', 'N/A')
                        port = tcp['port']
                        report_lines.append(f"{service.capitalize()} TCP ({port}): {status} ({time_ms}ms)")
                        
                # HTTP Requests
                for endpoint in ['frontend_http', 'backend_health', 'backend_api']:
                    if endpoint in results:
                        http = results[endpoint]
                        status = '✅' if http['success'] else '❌'
                        code = http.get('status_code', 'N/A')
                        time_ms = http.get('response_time', 'N/A')
                        report_lines.append(f"{endpoint.replace('_', ' ').title()}: {status} {code} ({time_ms}ms)")
                        
                # Database Security (external only)
                if 'database_security' in results:
                    db_sec = results['database_security']
                    postgres_status = '🔒 Blocked' if db_sec.get('postgres_5432_blocked') else '⚠️ EXPOSED'
                    redis_status = '🔒 Blocked' if db_sec.get('redis_6379_blocked') else '⚠️ EXPOSED'
                    report_lines.extend([
                        f"PostgreSQL (5432): {postgres_status}",
                        f"Redis (6379): {redis_status}"
                    ])
                    
                report_lines.append("")
                
        # Summary
        summary = self.results['summary']
        report_lines.extend([
            "SUMMARY:",
            "-" * 30,
            f"Localhost Healthy: {'✅' if summary['localhost_healthy'] else '❌'}",
            f"External Healthy: {'✅' if summary['external_healthy'] else '❌'}",
            f"Security Issues: {len(summary['security_issues'])}",
            f"Connectivity Issues: {len(summary['connectivity_issues'])}",
            ""
        ])
        
        # Issues
        if summary['connectivity_issues'] or summary['security_issues']:
            report_lines.append("ISSUES FOUND:")
            for issue in summary['connectivity_issues']:
                report_lines.append(f"  ❌ {issue}")
            for issue in summary['security_issues']:
                report_lines.append(f"  🚨 {issue}")
            report_lines.append("")
            
        # Recommendations
        if summary['recommendations']:
            report_lines.append("RECOMMENDATIONS:")
            for rec in summary['recommendations']:
                report_lines.append(f"  {rec}")
                
        report_lines.extend([
            "",
            "=" * 60,
            "End of Quick Connectivity Test Report",
            "=" * 60
        ])
        
        return "\n".join(report_lines)
        
    def run_all_tests(self):
        """Run all connectivity tests."""
        self.logger.info("🚀 Starting Quick Connectivity Test")
        self.logger.info("=" * 50)
        
        try:
            # Test localhost
            self.results['localhost'] = self.test_environment('localhost')
            
            # Test external
            self.results['external'] = self.test_environment('external')
            
            # Analyze results
            self.results['summary'] = self.analyze_results()
            
            # Generate report
            report = self.generate_report()
            
            # Save results
            with open('quick_connectivity_results.json', 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
                
            with open('quick_connectivity_report.txt', 'w') as f:
                f.write(report)
                
            print("\n" + report)
            
            # Exit with appropriate code
            if (self.results['summary']['localhost_healthy'] and 
                self.results['summary']['external_healthy'] and
                not self.results['summary']['security_issues']):
                self.logger.info("✅ All tests passed")
                return 0
            else:
                self.logger.error("❌ Some tests failed")
                return 1
                
        except Exception as e:
            self.logger.error(f"Test execution failed: {e}")
            return 1


if __name__ == "__main__":
    test_suite = QuickConnectivityTest()
    exit_code = test_suite.run_all_tests()
    sys.exit(exit_code)