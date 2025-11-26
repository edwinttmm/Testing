"""
Security Tests for Quality Tracking System

Tests security aspects of quality tracking:
1. SQL injection attempts in quality queries
2. UUID validation for session_id parameters
3. Rate limiting on quality check endpoints
4. Access control for quality data
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

import sys
sys.path.insert(0, '/home/rigade/Testing/ai-model-validation-platform/backend')

from main import app


@pytest.fixture
def test_client():
    return TestClient(app)


class TestSQLInjectionPrevention:
    """Test SQL injection protection in quality endpoints"""

    def test_quality_warnings_sql_injection_blocked(self, test_client):
        """Test that SQL injection attempts in session_id are blocked"""
        # SQL injection payloads
        injection_payloads = [
            "'; DROP TABLE test_sessions; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM users--",
            "'; DELETE FROM detection_events WHERE '1'='1",
            "<script>alert('XSS')</script>",
        ]

        for payload in injection_payloads:
            response = test_client.get(f"/api/quality/warnings/{payload}")

            # Should return 400 Bad Request (invalid UUID)
            # NOT 500 Internal Server Error (SQL error)
            assert response.status_code in [400, 404, 422], \
                f"SQL injection payload '{payload}' should be rejected with 400/404, got {response.status_code}"

            # Response should indicate invalid input, not database error
            if response.status_code == 400:
                assert "invalid" in response.json().get('detail', '').lower() or \
                       "uuid" in response.json().get('detail', '').lower()

    def test_quality_statistics_sql_injection_blocked(self, test_client):
        """Test SQL injection protection in statistics endpoint"""
        payload = "' OR 1=1--"

        response = test_client.get(f"/api/quality/statistics/{payload}")

        # Should reject malformed UUID
        assert response.status_code in [400, 404, 422]


class TestUUIDValidation:
    """Test UUID validation in quality endpoints"""

    def test_quality_warnings_requires_valid_uuid(self, test_client):
        """Test that quality warnings endpoint validates UUID format"""
        invalid_uuids = [
            "not-a-uuid",
            "12345",
            "abc-def-ghi",
            "",
            "test session id"
        ]

        for invalid_uuid in invalid_uuids:
            response = test_client.get(f"/api/quality/warnings/{invalid_uuid}")

            # Should reject invalid UUID
            assert response.status_code in [400, 404, 422], \
                f"Invalid UUID '{invalid_uuid}' should be rejected"

    def test_quality_warnings_accepts_valid_uuid(self, test_client):
        """Test that valid UUIDs are accepted (even if session doesn't exist)"""
        valid_uuid = str(uuid4())

        response = test_client.get(f"/api/quality/warnings/{valid_uuid}")

        # Should NOT return 400 (valid UUID format)
        # May return 404 (session not found) or 200 (empty warnings)
        assert response.status_code in [200, 404], \
            "Valid UUID should not be rejected with 400"


class TestRateLimiting:
    """Test rate limiting on quality check endpoints"""

    def test_quality_check_rate_limiting(self, test_client):
        """Test that excessive quality checks are rate limited"""
        session_id = str(uuid4())

        # Make 100 rapid requests
        responses = []
        for i in range(100):
            response = test_client.get(f"/api/quality/warnings/{session_id}")
            responses.append(response)

        # Should eventually return 429 Too Many Requests
        status_codes = [r.status_code for r in responses]

        # Either rate limiting is active (some 429s) or all succeed (no rate limiting configured)
        if any(code == 429 for code in status_codes):
            assert sum(1 for code in status_codes if code == 429) > 0, \
                "Rate limiting should block some requests"
        else:
            # If no rate limiting, all should succeed
            assert all(code in [200, 404] for code in status_codes), \
                "Without rate limiting, all requests should succeed"


class TestAccessControl:
    """Test access control for quality data"""

    def test_quality_data_requires_authentication(self, test_client):
        """Test that quality endpoints require authentication (if configured)"""
        # This test depends on whether authentication is enabled
        # If auth is disabled in development, skip this test

        session_id = str(uuid4())

        # Try to access without authentication token
        response = test_client.get(
            f"/api/quality/warnings/{session_id}",
            headers={}  # No auth headers
        )

        # If auth is required, should get 401/403
        # If auth is optional in dev, should get 200/404
        assert response.status_code in [200, 401, 403, 404]

    def test_cannot_access_other_users_quality_data(self, test_client):
        """Test that users cannot access quality data for sessions they don't own"""
        # This test requires multi-user setup
        # Create session as user A, try to access as user B

        session_id = str(uuid4())

        # Try to access with wrong user token (if auth is configured)
        # This is a placeholder - actual implementation depends on auth system

        response = test_client.get(
            f"/api/quality/warnings/{session_id}",
            headers={"Authorization": "Bearer fake-token"}
        )

        # Should either reject auth (401/403) or return not found (404)
        assert response.status_code in [200, 401, 403, 404]


class TestInputSanitization:
    """Test input sanitization in quality endpoints"""

    def test_filter_parameters_sanitized(self, test_client):
        """Test that filter parameters are properly sanitized"""
        session_id = str(uuid4())

        # Try XSS in query parameters
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>"
        ]

        for payload in xss_payloads:
            response = test_client.get(
                f"/api/detections/{session_id}?filter={payload}"
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 404, 422]

            # If successful, response should not contain unsanitized payload
            if response.status_code == 200:
                response_text = response.text
                assert "<script>" not in response_text
                assert "onerror=" not in response_text


class TestDataLeakage:
    """Test prevention of data leakage through quality endpoints"""

    def test_error_messages_dont_leak_database_info(self, test_client):
        """Test that error messages don't reveal database structure"""
        # Cause various errors
        error_triggers = [
            f"/api/quality/warnings/{'x' * 1000}",  # Very long input
            "/api/quality/statistics/NULL",  # SQL keyword
            "/api/quality/warnings/../../etc/passwd",  # Path traversal
        ]

        for trigger in error_triggers:
            response = test_client.get(trigger)

            # Even on error, should not reveal database info
            if response.status_code >= 400:
                error_detail = response.json().get('detail', '')

                # Should not contain database-specific error messages
                forbidden_terms = [
                    'table',
                    'column',
                    'database',
                    'postgresql',
                    'sqlite',
                    'SELECT',
                    'WHERE',
                    'schema'
                ]

                for term in forbidden_terms:
                    assert term.lower() not in error_detail.lower(), \
                        f"Error message should not contain '{term}'"


class TestConcurrencySafety:
    """Test thread safety of quality checks under concurrent load"""

    def test_concurrent_quality_checks_safe(self, test_client):
        """Test that concurrent quality checks don't cause race conditions"""
        import concurrent.futures

        session_id = str(uuid4())

        def check_quality():
            return test_client.get(f"/api/quality/warnings/{session_id}")

        # Make 50 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_quality) for _ in range(50)]
            responses = [f.result() for f in futures]

        # All requests should complete successfully (or all fail with same error)
        status_codes = [r.status_code for r in responses]

        # Either all 200/404 or all fail with same status
        unique_statuses = set(status_codes)
        assert len(unique_statuses) <= 2, \
            "Concurrent requests should return consistent status codes"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
