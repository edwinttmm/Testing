#!/usr/bin/env python3
"""
Penetration Testing Suite for Ground Truth System
Tests common attack vectors and security vulnerabilities
"""

import requests
import json
import time
import os
import tempfile
from typing import Dict, List, Any
from urllib.parse import urljoin
import base64

class PenetrationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = []
        
    def test_authentication_bypass(self) -> Dict[str, Any]:
        """Test for authentication bypass vulnerabilities"""
        test_results = {
            'test_name': 'Authentication Bypass',
            'status': 'FAILED',
            'vulnerabilities': [],
            'details': []
        }
        
        # Test endpoints that should require authentication
        protected_endpoints = [
            '/api/ground-truth/videos/available',
            '/api/ground-truth/videos/test-123/stats',
            '/api/videos/upload',
            '/api/projects'
        ]
        
        for endpoint in protected_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.get(url, timeout=10)
                
                if response.status_code != 401:
                    test_results['vulnerabilities'].append({
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'vulnerability': 'Missing Authentication',
                        'severity': 'CRITICAL'
                    })
                    test_results['details'].append(f"Endpoint {endpoint} accessible without authentication (HTTP {response.status_code})")
                    
            except requests.RequestException as e:
                test_results['details'].append(f"Error testing {endpoint}: {str(e)}")
                
        if test_results['vulnerabilities']:
            test_results['status'] = 'VULNERABLE'
        else:
            test_results['status'] = 'SECURE'
            
        return test_results
    
    def test_sql_injection(self) -> Dict[str, Any]:
        """Test for SQL injection vulnerabilities"""
        test_results = {
            'test_name': 'SQL Injection',
            'status': 'FAILED',
            'vulnerabilities': [],
            'details': []
        }
        
        # SQL injection payloads
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE videos; --",
            "' UNION SELECT * FROM auth_users --",
            "1' OR 1=1 --",
            "'; SELECT password FROM auth_users WHERE username='admin' --"
        ]
        
        # Test endpoints with parameters
        test_endpoints = [
            ('/api/ground-truth/videos/available', {'project_id': None, 'min_detections': None}),
            ('/api/ground-truth/videos/{}/stats', {'video_id': None}),
        ]
        
        for endpoint_template, params in test_endpoints:
            for param_name, param_value in params.items():
                for payload in sql_payloads:
                    try:
                        if param_name == 'video_id':
                            url = urljoin(self.base_url, endpoint_template.format(payload))
                            response = self.session.get(url, timeout=10)
                        else:
                            url = urljoin(self.base_url, endpoint_template)
                            params_dict = {param_name: payload}
                            response = self.session.get(url, params=params_dict, timeout=10)
                        
                        # Check for SQL error messages
                        sql_error_indicators = [
                            'sqlite3.OperationalError',
                            'SQL syntax',
                            'near \\"',
                            'database is locked',
                            'no such table',
                            'SQLITE_ERROR'
                        ]
                        
                        response_text = response.text.lower()
                        for indicator in sql_error_indicators:
                            if indicator.lower() in response_text:
                                test_results['vulnerabilities'].append({
                                    'endpoint': endpoint_template,
                                    'parameter': param_name,
                                    'payload': payload,
                                    'error_indicator': indicator,
                                    'severity': 'HIGH'
                                })
                                test_results['details'].append(f"SQL injection detected in {endpoint_template}:{param_name} with payload '{payload}'")
                                break
                                
                    except requests.RequestException as e:
                        continue
                        
        if test_results['vulnerabilities']:
            test_results['status'] = 'VULNERABLE'
        else:
            test_results['status'] = 'SECURE'
            
        return test_results
    
    def test_path_traversal(self) -> Dict[str, Any]:
        """Test for path traversal vulnerabilities"""
        test_results = {
            'test_name': 'Path Traversal',
            'status': 'FAILED',
            'vulnerabilities': [],
            'details': []
        }
        
        # Path traversal payloads
        path_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system.ini",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd"
        ]
        
        # Test file access endpoints
        file_endpoints = [
            '/api/videos/download/',
            '/api/static/',
            '/screenshots/',
            '/uploads/'
        ]
        
        for endpoint in file_endpoints:
            for payload in path_payloads:
                try:
                    url = urljoin(self.base_url, endpoint + payload)
                    response = self.session.get(url, timeout=10)
                    
                    # Check for successful file access indicators
                    sensitive_indicators = [
                        'root:x:0:0:',
                        '[fonts]',
                        'for 16-bit app support',
                        '/bin/bash',
                        '/etc/passwd'
                    ]
                    
                    response_text = response.text.lower()
                    for indicator in sensitive_indicators:
                        if indicator.lower() in response_text:
                            test_results['vulnerabilities'].append({
                                'endpoint': endpoint,
                                'payload': payload,
                                'indicator': indicator,
                                'severity': 'CRITICAL'
                            })
                            test_results['details'].append(f"Path traversal successful at {endpoint} with payload '{payload}'")
                            break
                            
                except requests.RequestException as e:
                    continue
                    
        if test_results['vulnerabilities']:
            test_results['status'] = 'VULNERABLE'
        else:
            test_results['status'] = 'SECURE'
            
        return test_results
    
    def test_file_upload_vulnerabilities(self) -> Dict[str, Any]:
        """Test file upload security"""
        test_results = {
            'test_name': 'File Upload Security',
            'status': 'FAILED',
            'vulnerabilities': [],
            'details': []
        }
        
        # Malicious file tests
        malicious_files = [
            ('shell.php', '<?php system($_GET["cmd"]); ?>', 'application/x-php'),
            ('script.js', 'alert("XSS")', 'application/javascript'),
            ('malware.exe', b'MZ\x90\x00\x03\x00\x00\x00', 'application/octet-stream'),
            ('large_file.txt', 'A' * (100 * 1024 * 1024), 'text/plain'),  # 100MB file
            ('double_ext.mp4.php', '<?php phpinfo(); ?>', 'video/mp4'),
        ]
        
        upload_endpoints = [
            '/api/videos/upload',
            '/api/upload'
        ]
        
        for endpoint in upload_endpoints:
            for filename, content, content_type in malicious_files:
                try:
                    url = urljoin(self.base_url, endpoint)
                    
                    if isinstance(content, str):
                        content = content.encode('utf-8')
                    
                    files = {'file': (filename, content, content_type)}
                    response = self.session.post(url, files=files, timeout=30)
                    
                    # Check if malicious file was accepted
                    if response.status_code in [200, 201, 202]:
                        test_results['vulnerabilities'].append({
                            'endpoint': endpoint,
                            'filename': filename,
                            'file_type': content_type,
                            'vulnerability': 'Malicious file accepted',
                            'severity': 'HIGH'
                        })
                        test_results['details'].append(f"Malicious file '{filename}' accepted at {endpoint}")
                        
                except requests.RequestException as e:
                    if 'timeout' in str(e).lower():
                        test_results['vulnerabilities'].append({
                            'endpoint': endpoint,
                            'filename': filename,
                            'vulnerability': 'Potential DoS via large file',
                            'severity': 'MEDIUM'
                        })
                        
        if test_results['vulnerabilities']:
            test_results['status'] = 'VULNERABLE'
        else:
            test_results['status'] = 'SECURE'
            
        return test_results
    
    def test_information_disclosure(self) -> Dict[str, Any]:
        """Test for information disclosure vulnerabilities"""
        test_results = {
            'test_name': 'Information Disclosure',
            'status': 'FAILED',
            'vulnerabilities': [],
            'details': []
        }
        
        # Test for detailed error messages
        error_endpoints = [
            ('/api/ground-truth/videos/nonexistent/stats', 'GET'),
            ('/api/projects/invalid-uuid', 'GET'),
            ('/api/videos/malformed-request', 'POST'),
        ]
        
        for endpoint, method in error_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                
                if method == 'GET':
                    response = self.session.get(url, timeout=10)
                else:
                    response = self.session.post(url, json={'invalid': 'data'}, timeout=10)
                
                # Check for information disclosure in error messages
                disclosure_indicators = [
                    'traceback',
                    'sqlalchemy',
                    'file not found',
                    'permission denied',
                    '/home/',
                    '/var/',
                    'line \\d+',
                    'exception',
                    'error processing video'
                ]
                
                response_text = response.text.lower()
                for indicator in disclosure_indicators:
                    if indicator in response_text:
                        test_results['vulnerabilities'].append({
                            'endpoint': endpoint,
                            'method': method,
                            'disclosure_type': indicator,
                            'severity': 'MEDIUM'
                        })
                        test_results['details'].append(f"Information disclosure at {endpoint}: {indicator}")
                        
            except requests.RequestException as e:
                continue
                
        if test_results['vulnerabilities']:
            test_results['status'] = 'VULNERABLE'
        else:
            test_results['status'] = 'SECURE'
            
        return test_results
    
    def test_denial_of_service(self) -> Dict[str, Any]:
        """Test for DoS vulnerabilities"""
        test_results = {
            'test_name': 'Denial of Service',
            'status': 'FAILED',
            'vulnerabilities': [],
            'details': []
        }
        
        # Test rate limiting
        endpoint = '/api/ground-truth/videos/available'
        url = urljoin(self.base_url, endpoint)
        
        try:
            # Send rapid requests
            start_time = time.time()
            responses = []
            
            for i in range(50):  # 50 rapid requests
                response = self.session.get(url, timeout=5)
                responses.append(response.status_code)
                
            end_time = time.time()
            duration = end_time - start_time
            
            # Check if all requests succeeded (no rate limiting)
            successful_requests = sum(1 for status in responses if status == 200)
            
            if successful_requests >= 45:  # Most requests succeeded
                test_results['vulnerabilities'].append({
                    'endpoint': endpoint,
                    'vulnerability': 'No rate limiting detected',
                    'successful_requests': successful_requests,
                    'total_requests': 50,
                    'duration': duration,
                    'severity': 'MEDIUM'
                })
                test_results['details'].append(f"No rate limiting: {successful_requests}/50 requests succeeded in {duration:.2f}s")
                
        except requests.RequestException as e:
            test_results['details'].append(f"DoS test failed: {str(e)}")
            
        # Test large request payloads
        try:
            large_payload = {'data': 'A' * (10 * 1024 * 1024)}  # 10MB payload
            response = self.session.post(url, json=large_payload, timeout=30)
            
            if response.status_code != 413:  # Payload too large
                test_results['vulnerabilities'].append({
                    'endpoint': endpoint,
                    'vulnerability': 'Large payloads accepted',
                    'payload_size': '10MB',
                    'severity': 'MEDIUM'
                })
                
        except requests.RequestException as e:
            if 'timeout' not in str(e).lower():
                test_results['details'].append(f"Large payload test error: {str(e)}")
                
        if test_results['vulnerabilities']:
            test_results['status'] = 'VULNERABLE'
        else:
            test_results['status'] = 'SECURE'
            
        return test_results
    
    def run_full_penetration_test(self) -> Dict[str, Any]:
        """Run complete penetration test suite"""
        print("🔍 Starting penetration testing suite...")
        
        tests = [
            self.test_authentication_bypass,
            self.test_sql_injection,
            self.test_path_traversal,
            self.test_file_upload_vulnerabilities,
            self.test_information_disclosure,
            self.test_denial_of_service,
        ]
        
        results = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'target': self.base_url,
            'tests': [],
            'summary': {
                'total_tests': len(tests),
                'vulnerable_tests': 0,
                'total_vulnerabilities': 0,
                'critical_vulnerabilities': 0,
                'high_vulnerabilities': 0,
                'medium_vulnerabilities': 0
            }
        }
        
        for test_func in tests:
            print(f"  🔍 Running {test_func.__name__}...")
            test_result = test_func()
            results['tests'].append(test_result)
            
            if test_result['status'] == 'VULNERABLE':
                results['summary']['vulnerable_tests'] += 1
                
            for vuln in test_result.get('vulnerabilities', []):
                results['summary']['total_vulnerabilities'] += 1
                severity = vuln.get('severity', 'MEDIUM').upper()
                if severity == 'CRITICAL':
                    results['summary']['critical_vulnerabilities'] += 1
                elif severity == 'HIGH':
                    results['summary']['high_vulnerabilities'] += 1
                elif severity == 'MEDIUM':
                    results['summary']['medium_vulnerabilities'] += 1
        
        # Determine overall risk
        if results['summary']['critical_vulnerabilities'] > 0:
            results['summary']['risk_level'] = 'CRITICAL'
        elif results['summary']['high_vulnerabilities'] > 0:
            results['summary']['risk_level'] = 'HIGH'
        elif results['summary']['medium_vulnerabilities'] > 0:
            results['summary']['risk_level'] = 'MEDIUM'
        else:
            results['summary']['risk_level'] = 'LOW'
            
        return results

def main():
    """Run penetration tests and save results"""
    tester = PenetrationTester()
    results = tester.run_full_penetration_test()
    
    # Save results
    output_file = '/home/rigade/Testing/ai-model-validation-platform/backend/security_audit/tests/penetration_test_results.json'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Penetration testing completed!")
    print(f"📊 Results saved to: {output_file}")
    print(f"\n📈 SUMMARY:")
    print(f"  Total Tests: {results['summary']['total_tests']}")
    print(f"  Vulnerable Tests: {results['summary']['vulnerable_tests']}")
    print(f"  Total Vulnerabilities: {results['summary']['total_vulnerabilities']}")
    print(f"  Critical: {results['summary']['critical_vulnerabilities']}")
    print(f"  High: {results['summary']['high_vulnerabilities']}")
    print(f"  Medium: {results['summary']['medium_vulnerabilities']}")
    print(f"  Risk Level: {results['summary']['risk_level']}")

if __name__ == "__main__":
    main()