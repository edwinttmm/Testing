#!/usr/bin/env python3
"""
Network Connectivity Testing for PostgreSQL Platform

Comprehensive network testing between Docker containers to ensure
proper communication between frontend, backend, PostgreSQL, and Redis services.

Features:
- Container-to-container connectivity testing
- DNS resolution validation
- Port accessibility checks
- Network latency measurements
- Docker network analysis
- Service discovery validation
"""

import os
import sys
import time
import json
import socket
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

try:
    import docker
    import psutil
    import ping3
except ImportError as e:
    print(f"Warning: Some network testing features may be limited: {e}")
    docker = None
    psutil = None
    ping3 = None

@dataclass
class NetworkTestResult:
    """Network test result structure"""
    test_name: str
    source: str
    destination: str
    success: bool
    latency_ms: Optional[float]
    error: Optional[str]
    details: Dict

class NetworkConnectivityTester:
    """Comprehensive network connectivity testing system"""
    
    def __init__(self):
        self.docker_client = None
        self.results = []
        self.config = self._load_config()
        
        # Initialize Docker client if available
        try:
            if docker:
                self.docker_client = docker.from_env()
        except Exception as e:
            print(f"Warning: Docker client unavailable: {e}")
    
    def _load_config(self) -> Dict:
        """Load network testing configuration"""
        return {
            'services': {
                'postgres': {
                    'container_name': 'postgres',
                    'port': 5432,
                    'service_name': 'PostgreSQL Database'
                },
                'backend': {
                    'container_name': 'backend', 
                    'port': 8000,
                    'service_name': 'FastAPI Backend'
                },
                'frontend': {
                    'container_name': 'frontend',
                    'port': 3000,
                    'service_name': 'React Frontend'
                },
                'redis': {
                    'container_name': 'redis',
                    'port': 6379,
                    'service_name': 'Redis Cache'
                }
            },
            'network_name': 'vru_validation_network',
            'timeout': 10,
            'retry_attempts': 3,
            'ping_count': 5
        }
    
    def get_container_network_info(self, container_name: str) -> Optional[Dict]:
        """Get network information for a specific container"""
        if not self.docker_client:
            return None
            
        try:
            container = self.docker_client.containers.get(container_name)
            networks = container.attrs['NetworkSettings']['Networks']
            
            network_info = {}
            for network_name, network_data in networks.items():
                network_info[network_name] = {
                    'ip_address': network_data.get('IPAddress'),
                    'gateway': network_data.get('Gateway'),
                    'subnet': network_data.get('MacAddress'),
                    'network_id': network_data.get('NetworkID')
                }
            
            return {
                'container_name': container_name,
                'status': container.status,
                'networks': network_info,
                'ports': container.ports,
                'hostname': container.attrs['Config']['Hostname']
            }
            
        except Exception as e:
            return {
                'container_name': container_name,
                'error': str(e),
                'status': 'not_found'
            }
    
    def test_dns_resolution(self, hostname: str, from_container: str = None) -> NetworkTestResult:
        """Test DNS resolution for hostnames"""
        start_time = time.time()
        
        try:
            if from_container and self.docker_client:
                # Test DNS resolution from inside a container
                container = self.docker_client.containers.get(from_container)
                
                # Execute nslookup inside container
                result = container.exec_run(
                    f"nslookup {hostname}",
                    stdout=True,
                    stderr=True
                )
                
                latency = (time.time() - start_time) * 1000
                
                if result.exit_code == 0:
                    output = result.output.decode('utf-8')
                    return NetworkTestResult(
                        test_name='dns_resolution',
                        source=from_container,
                        destination=hostname,
                        success=True,
                        latency_ms=round(latency, 2),
                        error=None,
                        details={'nslookup_output': output}
                    )
                else:
                    return NetworkTestResult(
                        test_name='dns_resolution',
                        source=from_container,
                        destination=hostname,
                        success=False,
                        latency_ms=round(latency, 2),
                        error=result.output.decode('utf-8'),
                        details={}
                    )
            else:
                # Test DNS resolution from host
                ip_address = socket.gethostbyname(hostname)
                latency = (time.time() - start_time) * 1000
                
                return NetworkTestResult(
                    test_name='dns_resolution',
                    source='host',
                    destination=hostname,
                    success=True,
                    latency_ms=round(latency, 2),
                    error=None,
                    details={'resolved_ip': ip_address}
                )
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return NetworkTestResult(
                test_name='dns_resolution',
                source=from_container or 'host',
                destination=hostname,
                success=False,
                latency_ms=round(latency, 2),
                error=str(e),
                details={}
            )
    
    def test_port_connectivity(self, host: str, port: int, from_container: str = None) -> NetworkTestResult:
        """Test port connectivity between containers or from host"""
        start_time = time.time()
        
        try:
            if from_container and self.docker_client:
                # Test connectivity from inside a container
                container = self.docker_client.containers.get(from_container)
                
                # Use netcat or telnet to test port
                result = container.exec_run(
                    f"timeout {self.config['timeout']} bash -c 'echo > /dev/tcp/{host}/{port}'",
                    stdout=True,
                    stderr=True
                )
                
                latency = (time.time() - start_time) * 1000
                
                success = result.exit_code == 0
                error = None if success else result.output.decode('utf-8')
                
                return NetworkTestResult(
                    test_name='port_connectivity',
                    source=from_container,
                    destination=f"{host}:{port}",
                    success=success,
                    latency_ms=round(latency, 2),
                    error=error,
                    details={'exit_code': result.exit_code}
                )
            else:
                # Test connectivity from host
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.config['timeout'])
                
                result = sock.connect_ex((host, port))
                sock.close()
                
                latency = (time.time() - start_time) * 1000
                success = result == 0
                
                return NetworkTestResult(
                    test_name='port_connectivity',
                    source='host',
                    destination=f"{host}:{port}",
                    success=success,
                    latency_ms=round(latency, 2),
                    error=None if success else f"Connection failed (code: {result})",
                    details={'socket_result': result}
                )
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return NetworkTestResult(
                test_name='port_connectivity',
                source=from_container or 'host',
                destination=f"{host}:{port}",
                success=False,
                latency_ms=round(latency, 2),
                error=str(e),
                details={}
            )
    
    def test_ping_connectivity(self, host: str, from_container: str = None) -> NetworkTestResult:
        """Test ICMP ping connectivity"""
        start_time = time.time()
        
        try:
            if from_container and self.docker_client:
                # Test ping from inside container
                container = self.docker_client.containers.get(from_container)
                
                result = container.exec_run(
                    f"ping -c {self.config['ping_count']} -W {self.config['timeout']} {host}",
                    stdout=True,
                    stderr=True
                )
                
                output = result.output.decode('utf-8')
                success = result.exit_code == 0
                
                # Parse ping results for latency
                avg_latency = None
                if success and 'rtt min/avg/max/mdev' in output:
                    try:
                        rtt_line = [line for line in output.split('\n') if 'rtt min/avg/max/mdev' in line][0]
                        avg_latency = float(rtt_line.split('/')[1])
                    except:
                        pass
                
                total_latency = (time.time() - start_time) * 1000
                
                return NetworkTestResult(
                    test_name='ping_connectivity',
                    source=from_container,
                    destination=host,
                    success=success,
                    latency_ms=avg_latency or round(total_latency, 2),
                    error=None if success else output,
                    details={
                        'ping_output': output,
                        'packets_sent': self.config['ping_count']
                    }
                )
            else:
                # Test ping from host using ping3 library or subprocess
                if ping3:
                    results = []
                    for _ in range(self.config['ping_count']):
                        ping_result = ping3.ping(host, timeout=self.config['timeout'])
                        if ping_result:
                            results.append(ping_result * 1000)  # Convert to ms
                    
                    if results:
                        avg_latency = sum(results) / len(results)
                        return NetworkTestResult(
                            test_name='ping_connectivity',
                            source='host',
                            destination=host,
                            success=True,
                            latency_ms=round(avg_latency, 2),
                            error=None,
                            details={
                                'min_latency': round(min(results), 2),
                                'max_latency': round(max(results), 2),
                                'packets_sent': self.config['ping_count'],
                                'packets_received': len(results)
                            }
                        )
                
                # Fallback to subprocess ping
                result = subprocess.run(
                    ['ping', '-c', str(self.config['ping_count']), '-W', str(self.config['timeout']), host],
                    capture_output=True,
                    text=True
                )
                
                success = result.returncode == 0
                total_latency = (time.time() - start_time) * 1000
                
                return NetworkTestResult(
                    test_name='ping_connectivity',
                    source='host',
                    destination=host,
                    success=success,
                    latency_ms=round(total_latency, 2),
                    error=None if success else result.stderr,
                    details={'ping_output': result.stdout}
                )
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return NetworkTestResult(
                test_name='ping_connectivity',
                source=from_container or 'host',
                destination=host,
                success=False,
                latency_ms=round(latency, 2),
                error=str(e),
                details={}
            )
    
    def test_service_health(self, service_name: str) -> NetworkTestResult:
        """Test service-specific health endpoints"""
        start_time = time.time()
        service_config = self.config['services'].get(service_name)
        
        if not service_config:
            return NetworkTestResult(
                test_name='service_health',
                source='host',
                destination=service_name,
                success=False,
                latency_ms=0,
                error=f"Unknown service: {service_name}",
                details={}
            )
        
        try:
            container_name = service_config['container_name']
            port = service_config['port']
            
            # Test different health check approaches based on service
            if service_name == 'postgres':
                # Test PostgreSQL connection
                try:
                    import psycopg2
                    conn = psycopg2.connect(
                        host='localhost',
                        port=port,
                        database='vru_validation',
                        user='postgres',
                        password='secure_password_change_me',
                        connect_timeout=self.config['timeout']
                    )
                    
                    cur = conn.cursor()
                    cur.execute('SELECT version();')
                    version = cur.fetchone()[0]
                    
                    cur.close()
                    conn.close()
                    
                    latency = (time.time() - start_time) * 1000
                    
                    return NetworkTestResult(
                        test_name='service_health',
                        source='host',
                        destination=f"{service_name}:{port}",
                        success=True,
                        latency_ms=round(latency, 2),
                        error=None,
                        details={'postgres_version': version}
                    )
                except Exception as e:
                    latency = (time.time() - start_time) * 1000
                    return NetworkTestResult(
                        test_name='service_health',
                        source='host',
                        destination=f"{service_name}:{port}",
                        success=False,
                        latency_ms=round(latency, 2),
                        error=str(e),
                        details={}
                    )
            
            elif service_name == 'backend':
                # Test FastAPI health endpoint
                try:
                    import requests
                    response = requests.get(
                        f"http://localhost:{port}/health",
                        timeout=self.config['timeout']
                    )
                    
                    latency = (time.time() - start_time) * 1000
                    
                    return NetworkTestResult(
                        test_name='service_health',
                        source='host',
                        destination=f"{service_name}:{port}/health",
                        success=response.status_code == 200,
                        latency_ms=round(latency, 2),
                        error=None if response.status_code == 200 else f"HTTP {response.status_code}",
                        details={
                            'status_code': response.status_code,
                            'response_data': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                        }
                    )
                except Exception as e:
                    latency = (time.time() - start_time) * 1000
                    return NetworkTestResult(
                        test_name='service_health',
                        source='host',
                        destination=f"{service_name}:{port}",
                        success=False,
                        latency_ms=round(latency, 2),
                        error=str(e),
                        details={}
                    )
            
            elif service_name == 'redis':
                # Test Redis connection
                try:
                    import redis
                    r = redis.Redis(
                        host='localhost',
                        port=port,
                        password='secure_redis_password',
                        socket_timeout=self.config['timeout']
                    )
                    
                    info = r.info()
                    latency = (time.time() - start_time) * 1000
                    
                    return NetworkTestResult(
                        test_name='service_health',
                        source='host',
                        destination=f"{service_name}:{port}",
                        success=True,
                        latency_ms=round(latency, 2),
                        error=None,
                        details={
                            'redis_version': info.get('redis_version'),
                            'connected_clients': info.get('connected_clients'),
                            'uptime_in_seconds': info.get('uptime_in_seconds')
                        }
                    )
                except Exception as e:
                    latency = (time.time() - start_time) * 1000
                    return NetworkTestResult(
                        test_name='service_health',
                        source='host',
                        destination=f"{service_name}:{port}",
                        success=False,
                        latency_ms=round(latency, 2),
                        error=str(e),
                        details={}
                    )
            
            else:
                # Generic port connectivity test
                return self.test_port_connectivity('localhost', port)
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return NetworkTestResult(
                test_name='service_health',
                source='host',
                destination=service_name,
                success=False,
                latency_ms=round(latency, 2),
                error=str(e),
                details={}
            )
    
    def test_inter_container_connectivity(self) -> List[NetworkTestResult]:
        """Test connectivity between all containers"""
        results = []
        services = list(self.config['services'].keys())
        
        # Test each service connecting to every other service
        for source_service in services:
            for target_service in services:
                if source_service == target_service:
                    continue
                
                source_container = self.config['services'][source_service]['container_name']
                target_container = self.config['services'][target_service]['container_name']
                target_port = self.config['services'][target_service]['port']
                
                # Test port connectivity
                result = self.test_port_connectivity(
                    target_container, 
                    target_port, 
                    from_container=source_container
                )
                results.append(result)
                
                # Test DNS resolution
                dns_result = self.test_dns_resolution(
                    target_container,
                    from_container=source_container
                )
                results.append(dns_result)
        
        return results
    
    def analyze_docker_network(self) -> Dict:
        """Analyze Docker network configuration"""
        if not self.docker_client:
            return {'error': 'Docker client not available'}
        
        try:
            network_name = self.config['network_name']
            networks = self.docker_client.networks.list(names=[network_name])
            
            if not networks:
                return {
                    'error': f'Network {network_name} not found',
                    'available_networks': [net.name for net in self.docker_client.networks.list()]
                }
            
            network = networks[0]
            network_info = network.attrs
            
            # Get connected containers
            containers = network_info.get('Containers', {})
            container_details = []
            
            for container_id, container_info in containers.items():
                try:
                    container = self.docker_client.containers.get(container_id)
                    container_details.append({
                        'name': container.name,
                        'ip_address': container_info.get('IPv4Address', '').split('/')[0],
                        'status': container.status,
                        'ports': container.ports
                    })
                except Exception as e:
                    container_details.append({
                        'name': container_info.get('Name', 'unknown'),
                        'error': str(e)
                    })
            
            return {
                'network_name': network.name,
                'driver': network_info.get('Driver'),
                'scope': network_info.get('Scope'),
                'subnet': network_info.get('IPAM', {}).get('Config', [{}])[0].get('Subnet'),
                'gateway': network_info.get('IPAM', {}).get('Config', [{}])[0].get('Gateway'),
                'containers': container_details,
                'container_count': len(container_details)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def run_comprehensive_network_test(self) -> Dict:
        """Run comprehensive network connectivity tests"""
        print("Starting comprehensive network connectivity tests...")
        
        all_results = []
        test_summary = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': 0,
            'successful_tests': 0,
            'failed_tests': 0,
            'average_latency_ms': 0,
            'test_categories': {},
            'network_analysis': {},
            'container_info': {},
            'recommendations': []
        }
        
        # Get network analysis
        test_summary['network_analysis'] = self.analyze_docker_network()
        
        # Get container network info for all services
        for service_name, service_config in self.config['services'].items():
            container_name = service_config['container_name']
            container_info = self.get_container_network_info(container_name)
            test_summary['container_info'][service_name] = container_info
        
        # Test 1: Service health checks
        print("Testing service health...")
        service_results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.test_service_health, service): service 
                for service in self.config['services'].keys()
            }
            
            for future in as_completed(futures):
                result = future.result()
                service_results.append(result)
                all_results.append(result)
        
        test_summary['test_categories']['service_health'] = {
            'total': len(service_results),
            'successful': sum(1 for r in service_results if r.success),
            'failed': sum(1 for r in service_results if not r.success),
            'results': [{
                'service': r.destination,
                'success': r.success,
                'latency_ms': r.latency_ms,
                'error': r.error
            } for r in service_results]
        }
        
        # Test 2: Inter-container connectivity  
        print("Testing inter-container connectivity...")
        inter_container_results = self.test_inter_container_connectivity()
        all_results.extend(inter_container_results)
        
        test_summary['test_categories']['inter_container'] = {
            'total': len(inter_container_results),
            'successful': sum(1 for r in inter_container_results if r.success),
            'failed': sum(1 for r in inter_container_results if not r.success)
        }
        
        # Test 3: Host-to-container connectivity
        print("Testing host-to-container connectivity...")
        host_results = []
        for service_name, service_config in self.config['services'].items():
            port_result = self.test_port_connectivity('localhost', service_config['port'])
            host_results.append(port_result)
            all_results.append(port_result)
        
        test_summary['test_categories']['host_to_container'] = {
            'total': len(host_results),
            'successful': sum(1 for r in host_results if r.success),
            'failed': sum(1 for r in host_results if not r.success)
        }
        
        # Calculate overall statistics
        test_summary['total_tests'] = len(all_results)
        test_summary['successful_tests'] = sum(1 for r in all_results if r.success)
        test_summary['failed_tests'] = test_summary['total_tests'] - test_summary['successful_tests']
        
        # Calculate average latency for successful tests
        successful_latencies = [r.latency_ms for r in all_results if r.success and r.latency_ms]
        if successful_latencies:
            test_summary['average_latency_ms'] = round(sum(successful_latencies) / len(successful_latencies), 2)
        
        # Generate recommendations
        recommendations = []
        if test_summary['failed_tests'] > 0:
            recommendations.append("Some network tests failed - check Docker container status")
        
        if test_summary['average_latency_ms'] > 100:
            recommendations.append("High network latency detected - check system performance")
        
        failed_services = [r.destination for r in service_results if not r.success]
        if failed_services:
            recommendations.append(f"Failed services: {', '.join(failed_services)} - check service configuration")
        
        network_analysis = test_summary['network_analysis']
        if 'error' in network_analysis:
            recommendations.append(f"Docker network issue: {network_analysis['error']}")
        
        test_summary['recommendations'] = recommendations
        test_summary['detailed_results'] = [
            {
                'test_name': r.test_name,
                'source': r.source,
                'destination': r.destination,
                'success': r.success,
                'latency_ms': r.latency_ms,
                'error': r.error,
                'details': r.details
            } for r in all_results
        ]
        
        return test_summary
    
    def save_test_results(self, results: Dict, filename: str = None) -> str:
        """Save test results to file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'/home/user/Testing/ai-model-validation-platform/backend/logs/network_test_{timestamp}.json'
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        return filename
    
    def generate_network_report(self, results: Dict) -> str:
        """Generate human-readable network test report"""
        report = []
        report.append("# Network Connectivity Test Report")
        report.append(f"Generated: {results['timestamp']}\n")
        
        # Overall summary
        success_rate = (results['successful_tests'] / results['total_tests']) * 100 if results['total_tests'] > 0 else 0
        report.append(f"## Overall Results")
        report.append(f"- Total Tests: {results['total_tests']}")
        report.append(f"- Successful: {results['successful_tests']}")
        report.append(f"- Failed: {results['failed_tests']}")
        report.append(f"- Success Rate: {success_rate:.1f}%")
        report.append(f"- Average Latency: {results['average_latency_ms']} ms\n")
        
        # Test categories
        report.append("## Test Categories")
        for category, data in results['test_categories'].items():
            cat_success_rate = (data['successful'] / data['total']) * 100 if data['total'] > 0 else 0
            report.append(f"### {category.replace('_', ' ').title()}")
            report.append(f"- Tests: {data['successful']}/{data['total']} ({cat_success_rate:.1f}% success)")
            
            if 'results' in data:
                for result in data['results']:
                    status = "✅" if result['success'] else "❌"
                    latency = f" ({result['latency_ms']}ms)" if result['latency_ms'] else ""
                    report.append(f"  - {status} {result['service']}{latency}")
                    if result['error']:
                        report.append(f"    Error: {result['error']}")
            report.append("")
        
        # Network analysis
        network = results['network_analysis']
        if 'error' not in network:
            report.append("## Docker Network Analysis")
            report.append(f"- Network: {network.get('network_name')}")
            report.append(f"- Driver: {network.get('driver')}")
            report.append(f"- Subnet: {network.get('subnet')}")
            report.append(f"- Gateway: {network.get('gateway')}")
            report.append(f"- Connected Containers: {network.get('container_count')}")
            
            if network.get('containers'):
                report.append("\n### Container Network Details")
                for container in network['containers']:
                    if 'error' not in container:
                        report.append(f"- {container['name']}: {container['ip_address']} ({container['status']})")
                    else:
                        report.append(f"- {container.get('name', 'unknown')}: Error - {container['error']}")
        else:
            report.append(f"## Network Analysis Error: {network['error']}")
        
        # Recommendations
        if results['recommendations']:
            report.append("\n## 🔧 Recommendations")
            for rec in results['recommendations']:
                report.append(f"- {rec}")
        
        # Quick fix commands
        if results['failed_tests'] > 0:
            report.append("\n## 🚑 Quick Fix Commands")
            report.append("```bash")
            report.append("# Check container status")
            report.append("docker-compose ps")
            report.append("")
            report.append("# Restart all services")
            report.append("cd /home/user/Testing/ai-model-validation-platform")
            report.append("docker-compose down && docker-compose up -d")
            report.append("")
            report.append("# Check network connectivity")
            report.append("docker network ls")
            report.append("docker network inspect vru_validation_network")
            report.append("```")
        
        return "\n".join(report)

def main():
    """Main network test execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Network Connectivity Test Tool')
    parser.add_argument('--output', help='Output file for results')
    parser.add_argument('--report', action='store_true', help='Generate human-readable report')
    parser.add_argument('--service', help='Test specific service only')
    parser.add_argument('--quick', action='store_true', help='Run quick connectivity test')
    
    args = parser.parse_args()
    
    tester = NetworkConnectivityTester()
    
    if args.service:
        # Test specific service
        result = tester.test_service_health(args.service)
        print(f"\n=== {args.service} Service Test ===")
        print(f"Status: {'✅ PASS' if result.success else '❌ FAIL'}")
        print(f"Latency: {result.latency_ms}ms")
        if result.error:
            print(f"Error: {result.error}")
        if result.details:
            print(f"Details: {json.dumps(result.details, indent=2)}")
    
    elif args.quick:
        # Quick connectivity test
        print("Running quick connectivity test...")
        for service_name in tester.config['services'].keys():
            result = tester.test_service_health(service_name)
            status = "✅" if result.success else "❌"
            latency = f" ({result.latency_ms}ms)" if result.latency_ms else ""
            print(f"{status} {service_name}{latency}")
    
    else:
        # Run comprehensive test
        results = tester.run_comprehensive_network_test()
        
        # Display summary
        success_rate = (results['successful_tests'] / results['total_tests']) * 100 if results['total_tests'] > 0 else 0
        print(f"\n=== Network Connectivity Test Results ===")
        print(f"Tests: {results['successful_tests']}/{results['total_tests']} ({success_rate:.1f}% success)")
        print(f"Average Latency: {results['average_latency_ms']}ms")
        
        if results['recommendations']:
            print(f"\n⚠️  Recommendations:")
            for rec in results['recommendations']:
                print(f"  - {rec}")
        
        # Save results
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'/home/user/Testing/ai-model-validation-platform/backend/logs/network_test_{timestamp}.json'
        
        saved_file = tester.save_test_results(results, output_file)
        print(f"\nResults saved to: {saved_file}")
        
        # Generate report if requested
        if args.report:
            report = tester.generate_network_report(results)
            report_file = saved_file.replace('.json', '_report.md')
            with open(report_file, 'w') as f:
                f.write(report)
            print(f"Report saved to: {report_file}")
            print(f"\n{report}")

if __name__ == '__main__':
    main()
