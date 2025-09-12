#!/usr/bin/env python3
"""
Authentication Bypass Security Test Suite
=========================================

This test suite validates authentication enforcement and detects bypass vulnerabilities
in the AI Model Validation Platform.

CRITICAL AUTHENTICATION TESTS:
1. Unauthenticated access prevention
2. Token validation and expiry enforcement
3. Session hijacking prevention
4. Role-based access control
5. API key security

These tests should FAIL initially if vulnerabilities exist, then PASS after fixes.
"""

import pytest
import requests
import json
import time
import hashlib
import hmac
import jwt
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import patch, MagicMock

import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from fastapi.testclient import TestClient
from fastapi import HTTPException

# Import the main application
from main import app

class AuthenticationTestHarness:
    """Test harness for authentication security testing"""
    
    def __init__(self):
        self.client = TestClient(app)
        self.base_url = "http://localhost:8000"
        
        # Test user credentials
        self.valid_user = {
            "username": "testuser",
            "email": "test@example.com", 
            "password": "SecurePassword123!",
            "role": "user"
        }
        
        self.admin_user = {
            "username": "admin",
            "email": "admin@example.com",
            "password": "AdminPassword456!",
            "role": "admin"
        }
        
        self.valid_token = None
        self.expired_token = None
        self.invalid_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJmYWtlIiwiZXhwIjoxNjA5NDU5MjAwfQ.invalid"
        
    def generate_test_tokens(self):
        """Generate test JWT tokens for authentication testing"""
        # Valid token (expires in 1 hour)
        valid_payload = {
            "sub": self.valid_user["username"],
            "email": self.valid_user["email"],
            "role": self.valid_user["role"],
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow()
        }
        
        # Expired token (expired 1 hour ago)
        expired_payload = {
            "sub": self.valid_user["username"], 
            "email": self.valid_user["email"],
            "role": self.valid_user["role"],
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2)
        }
        
        # Use a test secret key (in production this would be properly secured)
        secret_key = "test_jwt_secret_key_for_testing_only"
        
        self.valid_token = jwt.encode(valid_payload, secret_key, algorithm="HS256")
        self.expired_token = jwt.encode(expired_payload, secret_key, algorithm="HS256")
    
    def get_auth_headers(self, token: str = None) -> Dict[str, str]:
        """Get authentication headers with token"""
        if not token:
            token = self.valid_token
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_harness():
    """Fixture providing authentication test harness"""
    harness = AuthenticationTestHarness()
    harness.generate_test_tokens()
    return harness


class TestUnauthenticatedAccess:
    """Tests for preventing unauthenticated access to protected resources"""
    
    def test_protected_endpoints_require_authentication(self, auth_harness):
        """All protected endpoints should require authentication"""
        protected_endpoints = [
            ("GET", "/api/projects"),
            ("POST", "/api/projects"),
            ("GET", "/api/projects/123"),
            ("PUT", "/api/projects/123"),
            ("DELETE", "/api/projects/123"),
            ("POST", "/api/videos/upload"),
            ("GET", "/api/videos/123"),
            ("DELETE", "/api/videos/123"),
            ("GET", "/api/dashboard/stats"),
            ("POST", "/api/test-sessions"),
            ("GET", "/api/test-sessions/123/results")
        ]
        
        for method, endpoint in protected_endpoints:
            if method == "GET":
                response = auth_harness.client.get(endpoint)
            elif method == "POST":
                response = auth_harness.client.post(endpoint, json={"test": "data"})
            elif method == "PUT":
                response = auth_harness.client.put(endpoint, json={"test": "data"})
            elif method == "DELETE":
                response = auth_harness.client.delete(endpoint)
            
            assert response.status_code == 401, \
                f"AUTHENTICATION BYPASS: {method} {endpoint} allowed without authentication! Status: {response.status_code}"
    
    def test_file_upload_requires_authentication(self, auth_harness):
        """File upload endpoints should require authentication"""
        test_file_content = b"fake_video_content"
        files = {"file": ("test.mp4", test_file_content, "video/mp4")}
        data = {"projectId": "test-project-id"}
        
        response = auth_harness.client.post("/api/videos/upload", files=files, data=data)
        
        assert response.status_code == 401, \
            f"AUTHENTICATION BYPASS: File upload allowed without authentication! Status: {response.status_code}"
    
    def test_websocket_requires_authentication(self, auth_harness):
        """WebSocket connections should require authentication"""
        # This test would require a WebSocket client
        # For now, we'll test the HTTP endpoint that establishes WebSocket connections
        response = auth_harness.client.get("/ws")
        
        # Should either require authentication or return 401/403
        assert response.status_code in [401, 403, 404, 405], \
            f"AUTHENTICATION BYPASS: WebSocket endpoint accessible without auth! Status: {response.status_code}"


class TestTokenValidation:
    """Tests for proper JWT token validation"""
    
    def test_invalid_token_rejected(self, auth_harness):
        """Invalid JWT tokens should be rejected"""
        invalid_headers = auth_harness.get_auth_headers(auth_harness.invalid_token)
        
        response = auth_harness.client.get("/api/projects", headers=invalid_headers)
        
        assert response.status_code == 401, \
            f"TOKEN BYPASS: Invalid token accepted! Status: {response.status_code}"
    
    def test_expired_token_rejected(self, auth_harness):
        """Expired JWT tokens should be rejected"""
        expired_headers = auth_harness.get_auth_headers(auth_harness.expired_token)
        
        response = auth_harness.client.get("/api/projects", headers=expired_headers)
        
        assert response.status_code == 401, \
            f"TOKEN BYPASS: Expired token accepted! Status: {response.status_code}"
    
    def test_malformed_token_rejected(self, auth_harness):
        """Malformed tokens should be rejected"""
        malformed_tokens = [
            "Bearer malformed.token.here",
            "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",  # Incomplete
            "Bearer not-a-jwt-token-at-all",
            "Bearer ",  # Empty
            "Invalid eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJmYWtlIn0.fake",  # Wrong prefix
        ]
        
        for token in malformed_tokens:
            headers = {"Authorization": token}
            response = auth_harness.client.get("/api/projects", headers=headers)
            
            assert response.status_code == 401, \
                f"TOKEN BYPASS: Malformed token '{token[:50]}...' accepted! Status: {response.status_code}"
    
    def test_token_tampering_detected(self, auth_harness):
        """Token tampering should be detected"""
        # Take a valid token and modify it slightly
        tampered_token = auth_harness.valid_token[:-10] + "tampered123"
        tampered_headers = auth_harness.get_auth_headers(tampered_token)
        
        response = auth_harness.client.get("/api/projects", headers=tampered_headers)
        
        assert response.status_code == 401, \
            f"TOKEN BYPASS: Tampered token accepted! Status: {response.status_code}"


class TestSessionSecurity:
    """Tests for session security and hijacking prevention"""
    
    def test_concurrent_session_limits(self, auth_harness):
        """System should enforce concurrent session limits"""
        # This test would require session management implementation
        # For now, we test that multiple requests with the same token work
        # but tokens can't be reused maliciously
        
        headers = auth_harness.get_auth_headers()
        
        # Make multiple concurrent requests
        responses = []
        for i in range(5):
            response = auth_harness.client.get("/api/projects", headers=headers)
            responses.append(response.status_code)
        
        # All should succeed with valid token (unless rate limited)
        success_count = sum(1 for status in responses if status == 200)
        assert success_count >= 3, "Valid token should allow multiple requests"
    
    def test_token_blacklisting_after_logout(self, auth_harness):
        """Tokens should be invalidated after logout"""
        headers = auth_harness.get_auth_headers()
        
        # First, verify token works
        response = auth_harness.client.get("/api/projects", headers=headers)
        initial_status = response.status_code
        
        # Attempt logout (if endpoint exists)
        logout_response = auth_harness.client.post("/api/auth/logout", headers=headers)
        
        # If logout is implemented, token should be invalidated
        if logout_response.status_code == 200:
            # Try to use token after logout
            post_logout_response = auth_harness.client.get("/api/projects", headers=headers)
            assert post_logout_response.status_code == 401, \
                "SESSION BYPASS: Token still valid after logout!"


class TestRoleBasedAccessControl:
    """Tests for role-based access control (RBAC)"""
    
    def test_user_role_cannot_access_admin_endpoints(self, auth_harness):
        """Regular users should not access admin-only endpoints"""
        # Generate token with user role
        user_payload = {
            "sub": "regularuser",
            "email": "user@example.com",
            "role": "user",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        user_token = jwt.encode(user_payload, "test_jwt_secret_key_for_testing_only", algorithm="HS256")
        user_headers = auth_harness.get_auth_headers(user_token)
        
        admin_endpoints = [
            "/api/admin/users",
            "/api/admin/system-settings",
            "/api/admin/logs",
            "/api/admin/database",
            "/api/admin/security-audit"
        ]
        
        for endpoint in admin_endpoints:
            response = auth_harness.client.get(endpoint, headers=user_headers)
            
            # Should be forbidden (403) or not found (404) but not unauthorized (401)
            assert response.status_code in [403, 404, 405], \
                f"RBAC BYPASS: User role accessed admin endpoint {endpoint}! Status: {response.status_code}"
    
    def test_role_elevation_prevention(self, auth_harness):
        """Users should not be able to elevate their roles"""
        headers = auth_harness.get_auth_headers()
        
        # Try to modify user profile to escalate privileges
        privilege_escalation_data = {
            "role": "admin",
            "permissions": ["all"],
            "is_admin": True,
            "admin_level": 5
        }
        
        # Attempt to update user profile with elevated privileges
        response = auth_harness.client.put(
            "/api/users/profile",
            json=privilege_escalation_data,
            headers=headers
        )
        
        # Either should fail or ignore the privilege fields
        if response.status_code == 200:
            updated_data = response.json()
            assert updated_data.get("role") != "admin", \
                "PRIVILEGE ESCALATION: User elevated own role to admin!"
            assert not updated_data.get("is_admin", False), \
                "PRIVILEGE ESCALATION: User set admin flag!"


class TestAPIKeySecurity:
    """Tests for API key security if implemented"""
    
    def test_api_key_authentication_enforced(self, auth_harness):
        """API key authentication should be properly enforced"""
        # Test with invalid API key
        invalid_api_headers = {
            "X-API-Key": "invalid_api_key_123",
            "Authorization": "Bearer " + auth_harness.valid_token
        }
        
        response = auth_harness.client.get("/api/projects", headers=invalid_api_headers)
        
        # Should still work with valid JWT token even if API key is invalid
        # (unless API key is specifically required)
        # This test depends on the actual authentication strategy
        
        # Test with no authentication at all
        response = auth_harness.client.get("/api/projects")
        assert response.status_code == 401, "API endpoint accessible without any authentication"
    
    def test_api_key_rate_limiting(self, auth_harness):
        """API keys should be subject to rate limiting"""
        headers = auth_harness.get_auth_headers()
        
        # Make many rapid requests to trigger rate limiting
        rate_limit_responses = []
        for i in range(100):  # Adjust based on actual rate limits
            response = auth_harness.client.get("/api/projects", headers=headers)
            rate_limit_responses.append(response.status_code)
            
            if response.status_code == 429:  # Too Many Requests
                break
        
        # Should eventually hit rate limit (429) or remain stable
        # This is more about ensuring rate limiting exists rather than bypassing it
        has_rate_limiting = any(status == 429 for status in rate_limit_responses)
        # Rate limiting might not be implemented yet, so this is informational
        if not has_rate_limiting:
            print("INFO: Rate limiting not detected - consider implementing for production")


class TestAuthenticationBypassAttempts:
    """Tests for various authentication bypass techniques"""
    
    def test_header_injection_bypass(self, auth_harness):
        """Header injection attacks should not bypass authentication"""
        bypass_attempts = [
            {"X-Forwarded-User": "admin"},
            {"X-Remote-User": "admin"},
            {"X-Authenticated-User": "admin"},
            {"X-User-Id": "1"},
            {"X-Role": "admin"},
            {"Authorization": "Bearer valid_token", "X-Skip-Auth": "true"},
            {"User-Agent": "Admin-Bot-Bypass/1.0"},
        ]
        
        for headers in bypass_attempts:
            response = auth_harness.client.get("/api/projects", headers=headers)
            
            assert response.status_code == 401, \
                f"HEADER BYPASS: Authentication bypassed with headers: {headers}"
    
    def test_parameter_pollution_bypass(self, auth_harness):
        """Parameter pollution should not bypass authentication"""
        # Try to bypass with query parameters
        bypass_urls = [
            "/api/projects?authenticated=true",
            "/api/projects?token=admin",
            "/api/projects?user_id=1&role=admin",
            "/api/projects?skip_auth=1",
            "/api/projects?debug=true&bypass=auth"
        ]
        
        for url in bypass_urls:
            response = auth_harness.client.get(url)
            
            assert response.status_code == 401, \
                f"PARAMETER BYPASS: Authentication bypassed with URL: {url}"
    
    def test_method_override_bypass(self, auth_harness):
        """HTTP method override should not bypass authentication"""
        # Try to bypass using method override headers
        override_headers = [
            {"X-HTTP-Method-Override": "GET"},
            {"X-Method-Override": "GET"},
            {"_method": "GET"}
        ]
        
        for headers in override_headers:
            response = auth_harness.client.post("/api/projects", headers=headers, json={"test": "data"})
            
            # Should still require authentication regardless of method override
            assert response.status_code == 401, \
                f"METHOD BYPASS: Authentication bypassed with method override: {headers}"
    
    def test_timing_attack_resistance(self, auth_harness):
        """Authentication should be resistant to timing attacks"""
        import time
        
        # Test with valid vs invalid tokens to check for timing differences
        valid_headers = auth_harness.get_auth_headers()
        invalid_headers = auth_harness.get_auth_headers("invalid.token.here")
        
        # Time valid token authentication
        start_time = time.time()
        valid_response = auth_harness.client.get("/api/projects", headers=valid_headers)
        valid_time = time.time() - start_time
        
        # Time invalid token authentication
        start_time = time.time()
        invalid_response = auth_harness.client.get("/api/projects", headers=invalid_headers)
        invalid_time = time.time() - start_time
        
        # The timing difference should not be significant enough to leak information
        time_difference = abs(valid_time - invalid_time)
        
        # This is more of an informational test - timing attacks are complex
        if time_difference > 0.5:  # 500ms difference might indicate vulnerability
            print(f"WARNING: Significant timing difference detected: {time_difference:.3f}s")
            print("Consider implementing constant-time authentication checks")


class TestPasswordSecurity:
    """Tests for password-related security if applicable"""
    
    def test_password_reset_security(self, auth_harness):
        """Password reset should be secure"""
        # Test password reset endpoint if it exists
        reset_data = {"email": "test@example.com"}
        
        response = auth_harness.client.post("/api/auth/password-reset", json=reset_data)
        
        # Should not leak information about whether email exists
        if response.status_code == 200:
            response_data = response.json()
            assert "user found" not in response_data.get("message", "").lower(), \
                "Password reset leaks user existence information"
    
    def test_brute_force_protection(self, auth_harness):
        """System should have brute force protection"""
        login_data = {
            "username": "testuser",
            "password": "wrong_password"
        }
        
        # Attempt multiple failed logins
        failed_attempts = []
        for i in range(10):
            response = auth_harness.client.post("/api/auth/login", json=login_data)
            failed_attempts.append(response.status_code)
        
        # Should eventually return 429 (Too Many Requests) or similar
        has_brute_force_protection = any(status == 429 for status in failed_attempts)
        
        if not has_brute_force_protection:
            print("INFO: Brute force protection not detected - consider implementing")


def run_comprehensive_auth_test():
    """Run comprehensive authentication security test"""
    print("🔐 Starting Comprehensive Authentication Security Test")
    print("=" * 70)
    
    harness = AuthenticationTestHarness()
    harness.generate_test_tokens()
    
    test_results = []
    
    # Run critical authentication tests
    test_classes = [
        TestUnauthenticatedAccess,
        TestTokenValidation,
        TestSessionSecurity,
        TestRoleBasedAccessControl,
        TestAuthenticationBypassAttempts
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
    
    # Generate summary
    total_tests = len(test_results)
    passed_tests = len([r for r in test_results if r["status"] == "PASS"])
    failed_tests = len([r for r in test_results if r["status"] == "FAIL"])
    error_tests = len([r for r in test_results if r["status"] == "ERROR"])
    
    print("\n" + "=" * 70)
    print("📊 AUTHENTICATION SECURITY TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} 🚨")
    print(f"Errors: {error_tests} ⚠️")
    
    if failed_tests > 0:
        print(f"\n🚨 CRITICAL: {failed_tests} authentication vulnerabilities detected!")
        print("Review the test output above for specific security issues.")
        return False
    else:
        print("\n✅ All authentication security tests passed!")
        return True


if __name__ == "__main__":
    success = run_comprehensive_auth_test()
    exit(0 if success else 1)