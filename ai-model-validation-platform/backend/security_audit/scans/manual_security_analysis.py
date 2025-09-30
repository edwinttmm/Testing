#!/usr/bin/env python3
"""
Manual Security Analysis for Ground Truth System
Performs static code analysis without external dependencies
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
import glob

class ManualSecurityAnalyzer:
    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir)
        self.vulnerabilities = []
        
    def analyze_authentication_security(self) -> Dict[str, Any]:
        """Analyze authentication and authorization implementation"""
        findings = {
            'test_name': 'Authentication Security Analysis',
            'vulnerabilities': [],
            'files_analyzed': 0,
            'status': 'ANALYZING'
        }
        
        # Look for authentication patterns
        auth_patterns = {
            'missing_auth_decorator': {
                'pattern': r'@router\.(get|post|put|delete|patch)',
                'description': 'Endpoint without authentication dependency',
                'severity': 'CRITICAL'
            },
            'disabled_security': {
                'pattern': r'#.*security_middleware|#.*authentication',
                'description': 'Commented out security middleware',
                'severity': 'CRITICAL'
            },
            'anonymous_access': {
                'pattern': r'user_id.*=.*"anonymous"',
                'description': 'Default anonymous user access',
                'severity': 'HIGH'
            }
        }
        
        for py_file in self.target_dir.rglob('*.py'):
            findings['files_analyzed'] += 1
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for i, line in enumerate(lines, 1):
                    for vuln_type, config in auth_patterns.items():
                        if re.search(config['pattern'], line):
                            findings['vulnerabilities'].append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'vulnerability': vuln_type,
                                'description': config['description'],
                                'severity': config['severity']
                            })
            except Exception as e:
                continue
                
        findings['status'] = 'VULNERABLE' if findings['vulnerabilities'] else 'SECURE'
        return findings
    
    def analyze_file_upload_security(self) -> Dict[str, Any]:
        """Analyze file upload security implementation"""
        findings = {
            'test_name': 'File Upload Security Analysis',
            'vulnerabilities': [],
            'files_analyzed': 0,
            'status': 'ANALYZING'
        }
        
        # Look for file upload vulnerabilities
        upload_patterns = {
            'no_file_validation': {
                'pattern': r'UploadFile.*File',
                'description': 'File upload without validation',
                'severity': 'CRITICAL'
            },
            'unsafe_file_save': {
                'pattern': r'open\(.*file.*,.*[\'"]w',
                'description': 'Unsafe file write operation',
                'severity': 'HIGH'
            },
            'no_size_limit': {
                'pattern': r'MAX_FILE_SIZE|file\.size',
                'description': 'Missing file size validation',
                'severity': 'HIGH',
                'inverse': True  # Flag when NOT found
            }
        }
        
        upload_files = []
        for py_file in self.target_dir.rglob('*.py'):
            findings['files_analyzed'] += 1
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check if file handles uploads
                if 'UploadFile' in content or 'upload' in str(py_file).lower():
                    upload_files.append(py_file)
                    lines = content.split('\n')
                    
                    has_size_check = any('file.size' in line or 'MAX_FILE_SIZE' in line for line in lines)
                    has_type_check = any('filename' in line and ('extension' in line or 'mime' in line) for line in lines)
                    
                    if not has_size_check:
                        findings['vulnerabilities'].append({
                            'file': str(py_file.relative_to(self.target_dir)),
                            'vulnerability': 'missing_size_validation',
                            'description': 'No file size validation found',
                            'severity': 'HIGH'
                        })
                    
                    if not has_type_check:
                        findings['vulnerabilities'].append({
                            'file': str(py_file.relative_to(self.target_dir)),
                            'vulnerability': 'missing_type_validation',
                            'description': 'No file type validation found',
                            'severity': 'CRITICAL'
                        })
                        
                    for i, line in enumerate(lines, 1):
                        if 'UploadFile' in line and 'validate' not in line.lower():
                            findings['vulnerabilities'].append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'vulnerability': 'unvalidated_upload',
                                'description': 'File upload without validation',
                                'severity': 'CRITICAL'
                            })
                            
            except Exception as e:
                continue
                
        findings['upload_files_found'] = len(upload_files)
        findings['status'] = 'VULNERABLE' if findings['vulnerabilities'] else 'SECURE'
        return findings
    
    def analyze_sql_injection_risks(self) -> Dict[str, Any]:
        """Analyze SQL injection vulnerabilities"""
        findings = {
            'test_name': 'SQL Injection Risk Analysis',
            'vulnerabilities': [],
            'files_analyzed': 0,
            'status': 'ANALYZING'
        }
        
        sql_patterns = {
            'string_concatenation': {
                'pattern': r'\.query\([^)]*\+|\.filter\([^)]*\+',
                'description': 'SQL query with string concatenation',
                'severity': 'HIGH'
            },
            'format_string': {
                'pattern': r'\.query\([^)]*format\(|\.filter\([^)]*format\(',
                'description': 'SQL query with string formatting',
                'severity': 'HIGH'
            },
            'direct_execution': {
                'pattern': r'execute\([^)]*\+|execute\([^)]*format\(',
                'description': 'Direct SQL execution with concatenation',
                'severity': 'CRITICAL'
            },
            'text_concatenation': {
                'pattern': r'text\([^)]*\+',
                'description': 'SQL text() with concatenation',
                'severity': 'HIGH'
            }
        }
        
        for py_file in self.target_dir.rglob('*.py'):
            findings['files_analyzed'] += 1
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for i, line in enumerate(lines, 1):
                    for vuln_type, config in sql_patterns.items():
                        if re.search(config['pattern'], line):
                            findings['vulnerabilities'].append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'vulnerability': vuln_type,
                                'description': config['description'],
                                'severity': config['severity']
                            })
            except Exception as e:
                continue
                
        findings['status'] = 'VULNERABLE' if findings['vulnerabilities'] else 'SECURE'
        return findings
    
    def analyze_path_traversal_risks(self) -> Dict[str, Any]:
        """Analyze path traversal vulnerabilities"""
        findings = {
            'test_name': 'Path Traversal Risk Analysis',
            'vulnerabilities': [],
            'files_analyzed': 0,
            'status': 'ANALYZING'
        }
        
        path_patterns = {
            'unsafe_path_join': {
                'pattern': r'os\.path\.join\([^)]*\+|Path\([^)]*\+',
                'description': 'Unsafe path construction with concatenation',
                'severity': 'HIGH'
            },
            'direct_file_access': {
                'pattern': r'open\([^)]*\+|cv2\.imwrite\([^)]*\+',
                'description': 'Direct file access with concatenation',
                'severity': 'HIGH'
            },
            'user_controlled_path': {
                'pattern': r'file_path.*request\.|video_file_path.*\+',
                'description': 'User-controlled file path construction',
                'severity': 'CRITICAL'
            }
        }
        
        for py_file in self.target_dir.rglob('*.py'):
            findings['files_analyzed'] += 1
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for i, line in enumerate(lines, 1):
                    for vuln_type, config in path_patterns.items():
                        if re.search(config['pattern'], line):
                            findings['vulnerabilities'].append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'vulnerability': vuln_type,
                                'description': config['description'],
                                'severity': config['severity']
                            })
            except Exception as e:
                continue
                
        findings['status'] = 'VULNERABLE' if findings['vulnerabilities'] else 'SECURE'
        return findings
    
    def analyze_information_disclosure(self) -> Dict[str, Any]:
        """Analyze information disclosure vulnerabilities"""
        findings = {
            'test_name': 'Information Disclosure Analysis',
            'vulnerabilities': [],
            'files_analyzed': 0,
            'status': 'ANALYZING'
        }
        
        disclosure_patterns = {
            'detailed_exceptions': {
                'pattern': r'detail=.*str\(e\)|detail=.*\{.*e.*\}',
                'description': 'Detailed exception in HTTP response',
                'severity': 'MEDIUM'
            },
            'stack_trace_logging': {
                'pattern': r'logger\.exception|traceback\.print_exc',
                'description': 'Stack trace logging (potential disclosure)',
                'severity': 'LOW'
            },
            'path_disclosure': {
                'pattern': r'f.*/{.*}|file_path.*{|path.*{',
                'description': 'File path in string formatting',
                'severity': 'MEDIUM'
            },
            'debug_information': {
                'pattern': r'print\(|debug.*=.*True',
                'description': 'Debug information in production code',
                'severity': 'LOW'
            }
        }
        
        for py_file in self.target_dir.rglob('*.py'):
            findings['files_analyzed'] += 1
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for i, line in enumerate(lines, 1):
                    for vuln_type, config in disclosure_patterns.items():
                        if re.search(config['pattern'], line):
                            findings['vulnerabilities'].append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'vulnerability': vuln_type,
                                'description': config['description'],
                                'severity': config['severity']
                            })
            except Exception as e:
                continue
                
        findings['status'] = 'VULNERABLE' if findings['vulnerabilities'] else 'SECURE'
        return findings
    
    def analyze_configuration_security(self) -> Dict[str, Any]:
        """Analyze security configuration issues"""
        findings = {
            'test_name': 'Configuration Security Analysis',
            'vulnerabilities': [],
            'files_analyzed': 0,
            'status': 'ANALYZING'
        }
        
        config_patterns = {
            'disabled_security': {
                'pattern': r'#.*security|#.*auth|Temporarily disable',
                'description': 'Security features commented out or disabled',
                'severity': 'CRITICAL'
            },
            'hardcoded_secrets': {
                'pattern': r'password.*=.*["\'].*["\']|secret.*=.*["\'].*["\']|key.*=.*["\'].*["\']',
                'description': 'Potential hardcoded credentials',
                'severity': 'HIGH'
            },
            'debug_mode': {
                'pattern': r'debug.*=.*True|DEBUG.*=.*True',
                'description': 'Debug mode enabled',
                'severity': 'MEDIUM'
            }
        }
        
        for py_file in self.target_dir.rglob('*.py'):
            findings['files_analyzed'] += 1
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                for i, line in enumerate(lines, 1):
                    for vuln_type, config in config_patterns.items():
                        if re.search(config['pattern'], line, re.IGNORECASE):
                            findings['vulnerabilities'].append({
                                'file': str(py_file.relative_to(self.target_dir)),
                                'line': i,
                                'code': line.strip(),
                                'vulnerability': vuln_type,
                                'description': config['description'],
                                'severity': config['severity']
                            })
            except Exception as e:
                continue
                
        findings['status'] = 'VULNERABLE' if findings['vulnerabilities'] else 'SECURE'
        return findings
    
    def generate_summary(self, all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive security summary"""
        total_vulnerabilities = 0
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0
        
        vulnerable_tests = 0
        total_tests = len(all_results)
        
        for result in all_results:
            if result['status'] == 'VULNERABLE':
                vulnerable_tests += 1
                
            for vuln in result.get('vulnerabilities', []):
                total_vulnerabilities += 1
                severity = vuln.get('severity', 'UNKNOWN').upper()
                
                if severity == 'CRITICAL':
                    critical_count += 1
                elif severity == 'HIGH':
                    high_count += 1
                elif severity == 'MEDIUM':
                    medium_count += 1
                elif severity == 'LOW':
                    low_count += 1
        
        # Determine overall risk level
        if critical_count > 0:
            risk_level = 'CRITICAL'
        elif high_count > 0:
            risk_level = 'HIGH'
        elif medium_count > 0:
            risk_level = 'MEDIUM'
        elif low_count > 0:
            risk_level = 'LOW'
        else:
            risk_level = 'MINIMAL'
        
        return {
            'total_tests': total_tests,
            'vulnerable_tests': vulnerable_tests,
            'total_vulnerabilities': total_vulnerabilities,
            'critical_vulnerabilities': critical_count,
            'high_vulnerabilities': high_count,
            'medium_vulnerabilities': medium_count,
            'low_vulnerabilities': low_count,
            'risk_level': risk_level,
            'security_score': max(0, 100 - (critical_count * 25 + high_count * 10 + medium_count * 5 + low_count * 1))
        }
    
    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run all security analyses"""
        print("🔍 Starting manual security analysis...")
        
        analyses = [
            ('Authentication Security', self.analyze_authentication_security),
            ('File Upload Security', self.analyze_file_upload_security),
            ('SQL Injection Risks', self.analyze_sql_injection_risks),
            ('Path Traversal Risks', self.analyze_path_traversal_risks),
            ('Information Disclosure', self.analyze_information_disclosure),
            ('Configuration Security', self.analyze_configuration_security),
        ]
        
        results = {
            'scan_timestamp': '2025-01-29T12:00:00Z',
            'target_directory': str(self.target_dir),
            'scan_type': 'Manual Static Analysis',
            'analyses': []
        }
        
        all_analysis_results = []
        
        for name, analysis_func in analyses:
            print(f"  🔍 Running {name}...")
            result = analysis_func()
            results['analyses'].append(result)
            all_analysis_results.append(result)
        
        # Generate summary
        summary = self.generate_summary(all_analysis_results)
        results['summary'] = summary
        
        return results

def main():
    """Run manual security analysis"""
    target_dir = '/home/rigade/Testing/ai-model-validation-platform/backend'
    
    analyzer = ManualSecurityAnalyzer(target_dir)
    results = analyzer.run_comprehensive_analysis()
    
    # Save results
    output_file = '/home/rigade/Testing/ai-model-validation-platform/backend/security_audit/scans/manual_analysis_results.json'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Manual security analysis completed!")
    print(f"📊 Results saved to: {output_file}")
    print(f"\n📈 SUMMARY:")
    print(f"  Total Tests: {results['summary']['total_tests']}")
    print(f"  Vulnerable Tests: {results['summary']['vulnerable_tests']}")
    print(f"  Total Vulnerabilities: {results['summary']['total_vulnerabilities']}")
    print(f"  Critical: {results['summary']['critical_vulnerabilities']}")
    print(f"  High: {results['summary']['high_vulnerabilities']}")
    print(f"  Medium: {results['summary']['medium_vulnerabilities']}")
    print(f"  Low: {results['summary']['low_vulnerabilities']}")
    print(f"  Risk Level: {results['summary']['risk_level']}")
    print(f"  Security Score: {results['summary']['security_score']}/100")
    
    # Display key findings
    print(f"\n🚨 KEY SECURITY FINDINGS:")
    for analysis in results['analyses']:
        if analysis['status'] == 'VULNERABLE':
            print(f"  ❌ {analysis['test_name']}: {len(analysis['vulnerabilities'])} vulnerabilities")
            # Show top 3 most severe
            vulns = sorted(analysis['vulnerabilities'], 
                          key=lambda x: {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}.get(x.get('severity', 'LOW'), 0), 
                          reverse=True)
            for vuln in vulns[:3]:
                print(f"    - {vuln.get('description', 'Unknown vulnerability')} [{vuln.get('severity', 'UNKNOWN')}]")
        else:
            print(f"  ✅ {analysis['test_name']}: No vulnerabilities detected")
    
    return results

if __name__ == "__main__":
    main()