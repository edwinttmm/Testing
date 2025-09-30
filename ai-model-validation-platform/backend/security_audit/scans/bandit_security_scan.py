#!/usr/bin/env python3
"""
Security Scanner for Ground Truth System
Uses multiple security analysis tools to identify vulnerabilities
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
import tempfile
import re

class SecurityScanner:
    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir)
        self.results = {}
        
    def run_bandit_scan(self) -> Dict[str, Any]:
        """Run Bandit security scanner for Python code"""
        try:
            cmd = [
                'bandit', '-r', str(self.target_dir),
                '-f', 'json',
                '--skip', 'B101',  # Skip assert_used test for testing code
                '--exclude', '*/tests/*,*/venv/*,*/__pycache__/*'
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300
            )
            
            if result.returncode == 0 or result.returncode == 1:  # Bandit returns 1 when issues found
                return {
                    'status': 'success',
                    'data': json.loads(result.stdout),
                    'stderr': result.stderr
                }
            else:
                return {
                    'status': 'error',
                    'error': result.stderr,
                    'stdout': result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'error': 'Bandit scan timed out'}
        except FileNotFoundError:
            return {'status': 'not_found', 'error': 'Bandit not installed'}
        except json.JSONDecodeError as e:
            return {'status': 'json_error', 'error': str(e), 'stdout': result.stdout}
        except Exception as e:
            return {'status': 'exception', 'error': str(e)}
    
    def analyze_sql_injection_risks(self) -> Dict[str, Any]:
        """Custom analysis for SQL injection vulnerabilities"""
        sql_injection_patterns = [
            r'\.query\([^)]*\+',  # String concatenation in queries
            r'\.filter\([^)]*format\(',  # String formatting in filters
            r'\.filter\([^)]*%',  # String interpolation
            r'execute\([^)]*\+',  # String concatenation in execute
            r'execute\([^)]*format\(',  # String formatting in execute
            r'text\([^)]*\+',  # String concatenation in text()
        ]
        
        vulnerabilities = []
        
        for py_file in self.target_dir.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for i, line in enumerate(lines, 1):
                    for pattern in sql_injection_patterns:
                        if re.search(pattern, line):
                            vulnerabilities.append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'pattern': pattern,
                                'severity': 'HIGH',
                                'type': 'SQL_INJECTION_RISK'
                            })
            except Exception as e:
                continue
                
        return {
            'status': 'success',
            'vulnerabilities': vulnerabilities,
            'count': len(vulnerabilities)
        }
    
    def analyze_path_traversal_risks(self) -> Dict[str, Any]:
        """Custom analysis for path traversal vulnerabilities"""
        path_traversal_patterns = [
            r'os\.path\.join\([^)]*request\.',  # Direct request data in path join
            r'os\.path\.join\([^)]*\+',  # String concatenation with path join
            r'open\([^)]*\+',  # String concatenation in file open
            r'Path\([^)]*\+',  # String concatenation with Path
            r'/\.\./|\.\./',  # Direct path traversal sequences
            r'file_path.*\+',  # file_path variable concatenation
        ]
        
        vulnerabilities = []
        
        for py_file in self.target_dir.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for i, line in enumerate(lines, 1):
                    for pattern in path_traversal_patterns:
                        if re.search(pattern, line):
                            vulnerabilities.append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'pattern': pattern,
                                'severity': 'HIGH',
                                'type': 'PATH_TRAVERSAL_RISK'
                            })
            except Exception as e:
                continue
                
        return {
            'status': 'success',
            'vulnerabilities': vulnerabilities,
            'count': len(vulnerabilities)
        }
    
    def analyze_authentication_issues(self) -> Dict[str, Any]:
        """Analyze authentication and authorization issues"""
        auth_issues = []
        
        # Look for endpoints without authentication
        endpoint_patterns = [
            r'@router\.(get|post|put|delete|patch)',
            r'@app\.(get|post|put|delete|patch)',
        ]
        
        auth_patterns = [
            r'Depends\(.*auth',
            r'current_user',
            r'get_current_user',
            r'authenticate',
        ]
        
        for py_file in self.target_dir.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                in_endpoint = False
                endpoint_line = 0
                
                for i, line in enumerate(lines, 1):
                    # Check for endpoint definition
                    for pattern in endpoint_patterns:
                        if re.search(pattern, line):
                            in_endpoint = True
                            endpoint_line = i
                            break
                    
                    # If in endpoint, look for auth in next few lines
                    if in_endpoint and i <= endpoint_line + 5:
                        has_auth = any(re.search(auth_pattern, line) for auth_pattern in auth_patterns)
                        if has_auth:
                            in_endpoint = False
                            break
                    elif in_endpoint and i > endpoint_line + 5:
                        # No auth found in reasonable distance
                        auth_issues.append({
                            'file': str(py_file.relative_to(self.target_dir)),
                            'line': endpoint_line,
                            'severity': 'CRITICAL',
                            'type': 'MISSING_AUTHENTICATION',
                            'description': 'Endpoint lacks authentication'
                        })
                        in_endpoint = False
                        
            except Exception as e:
                continue
                
        return {
            'status': 'success',
            'issues': auth_issues,
            'count': len(auth_issues)
        }
    
    def analyze_hardcoded_secrets(self) -> Dict[str, Any]:
        """Look for hardcoded secrets and credentials"""
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'key\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'database.*://.*:.*@',
        ]
        
        secrets = []
        
        for py_file in self.target_dir.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for i, line in enumerate(lines, 1):
                    for pattern in secret_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            secrets.append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'pattern': pattern,
                                'severity': 'HIGH',
                                'type': 'HARDCODED_SECRET'
                            })
            except Exception as e:
                continue
                
        return {
            'status': 'success',
            'secrets': secrets,
            'count': len(secrets)
        }
    
    def run_comprehensive_scan(self) -> Dict[str, Any]:
        """Run all security scans and compile results"""
        print("🔍 Starting comprehensive security scan...")
        
        # Run Bandit scan
        print("  🔍 Running Bandit security scanner...")
        bandit_results = self.run_bandit_scan()
        
        # Run custom analyses
        print("  🔍 Analyzing SQL injection risks...")
        sql_results = self.analyze_sql_injection_risks()
        
        print("  🔍 Analyzing path traversal risks...")
        path_results = self.analyze_path_traversal_risks()
        
        print("  🔍 Analyzing authentication issues...")
        auth_results = self.analyze_authentication_issues()
        
        print("  🔍 Analyzing hardcoded secrets...")
        secret_results = self.analyze_hardcoded_secrets()
        
        # Compile comprehensive results
        results = {
            'scan_timestamp': '2025-01-29T10:00:00Z',
            'target_directory': str(self.target_dir),
            'scans': {
                'bandit': bandit_results,
                'sql_injection': sql_results,
                'path_traversal': path_results,
                'authentication': auth_results,
                'secrets': secret_results
            },
            'summary': self._generate_summary(
                bandit_results, sql_results, path_results, auth_results, secret_results
            )
        }
        
        return results
    
    def _generate_summary(self, bandit, sql, path, auth, secrets) -> Dict[str, Any]:
        """Generate summary of security scan results"""
        total_issues = 0
        critical_issues = 0
        high_issues = 0
        medium_issues = 0
        
        # Count Bandit issues
        if bandit.get('status') == 'success' and 'data' in bandit:
            bandit_issues = bandit['data'].get('results', [])
            total_issues += len(bandit_issues)
            for issue in bandit_issues:
                severity = issue.get('issue_severity', '').upper()
                if severity == 'HIGH':
                    high_issues += 1
                elif severity == 'MEDIUM':
                    medium_issues += 1
        
        # Count custom analysis issues
        if sql.get('status') == 'success':
            total_issues += sql.get('count', 0)
            high_issues += sql.get('count', 0)  # SQL injection is always high
            
        if path.get('status') == 'success':
            total_issues += path.get('count', 0)
            high_issues += path.get('count', 0)  # Path traversal is always high
            
        if auth.get('status') == 'success':
            total_issues += auth.get('count', 0)
            critical_issues += auth.get('count', 0)  # Missing auth is critical
            
        if secrets.get('status') == 'success':
            total_issues += secrets.get('count', 0)
            high_issues += secrets.get('count', 0)  # Hardcoded secrets are high
        
        return {
            'total_issues': total_issues,
            'critical_issues': critical_issues,
            'high_issues': high_issues,
            'medium_issues': medium_issues,
            'risk_level': 'CRITICAL' if critical_issues > 0 else 'HIGH' if high_issues > 0 else 'MEDIUM' if medium_issues > 0 else 'LOW'
        }

def main():
    # Set target directory
    target_dir = '/home/rigade/Testing/ai-model-validation-platform/backend'
    
    scanner = SecurityScanner(target_dir)
    results = scanner.run_comprehensive_scan()
    
    # Save results
    output_file = '/home/rigade/Testing/ai-model-validation-platform/backend/security_audit/scans/security_scan_results.json'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Security scan completed!")
    print(f"📊 Results saved to: {output_file}")
    print(f"\n📈 SUMMARY:")
    print(f"  Total Issues: {results['summary']['total_issues']}")
    print(f"  Critical: {results['summary']['critical_issues']}")
    print(f"  High: {results['summary']['high_issues']}")
    print(f"  Medium: {results['summary']['medium_issues']}")
    print(f"  Risk Level: {results['summary']['risk_level']}")
    
    return results

if __name__ == "__main__":
    main()