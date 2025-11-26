"""
Comprehensive Security Implementation Tests

Tests all security features implemented:
1. UUID validation (SQL injection prevention)
2. Rate limiting (DoS prevention)
3. Session ownership verification (unauthorized access prevention)
4. Connection leak prevention

Author: Security Implementation Specialist
Date: 2025-11-19
"""

import pytest
import time
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import uuid as uuid_lib

# Import security utilities
from utils.validation import validate_uuid, ValidationError
from utils.security import verify_session_ownership, verify_sequence_ownership, SecurityError
from utils.rate_limiter import RateLimiter
from utils.db_utils import managed_db_session, DatabaseSessionManager
from middleware.auto_security import AutoSecurityMiddleware

# Import models
from models import TestSession, VideoTestSequence, Project


class TestUUIDValidation:
    """Test UUID validation for SQL injection prevention"""

    def test_valid_uuid_lowercase(self):
        """Valid lowercase UUID should pass"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = validate_uuid(valid_uuid, "test_id")
        assert result == valid_uuid.lower()

    def test_valid_uuid_uppercase(self):
        """Valid uppercase UUID should pass and be converted to lowercase"""
        valid_uuid = "123E4567-E89B-12D3-A456-426614174000"
        result = validate_uuid(valid_uuid, "test_id")
        assert result == valid_uuid.lower()

    def test_valid_uuid_mixed_case(self):
        """Valid mixed case UUID should pass"""
        valid_uuid = "123e4567-E89B-12d3-A456-426614174000"
        result = validate_uuid(valid_uuid, "test_id")
        assert result == valid_uuid.lower()

    def test_empty_uuid_rejected(self):
        """Empty UUID should be rejected"""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("", "test_id")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot be empty" in exc_info.value.detail

    def test_none_uuid_rejected(self):
        """None UUID should be rejected"""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid(None, "test_id")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_wrong_length_rejected(self):
        """UUID with wrong length should be rejected"""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("123e4567-e89b-12d3-a456", "test_id")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "36 characters" in exc_info.value.detail

    def test_sql_injection_attempt_rejected(self):
        """SQL injection attempts should be rejected"""
        malicious_inputs = [
            "' OR '1'='1",
            "1; DROP TABLE users--",
            "admin'--",
            "' UNION SELECT * FROM users--",
            "../../../etc/passwd",
            "<script>alert('xss')</script>",
            "'; EXEC xp_cmdshell('dir'); --"
        ]

        for malicious in malicious_inputs:
            with pytest.raises(HTTPException) as exc_info:
                validate_uuid(malicious, "test_id")
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid" in exc_info.value.detail or "36 characters" in exc_info.value.detail

    def test_invalid_uuid_format_rejected(self):
        """Invalid UUID format should be rejected"""
        invalid_uuids = [
            "not-a-uuid-at-all-really-not-a-uuid",  # Wrong format
            "123e4567-e89b-12d3-a456-42661417400",   # Too short
            "123e4567-e89b-12d3-a456-4266141740000", # Too long
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # Invalid characters
            "123e4567e89b12d3a456426614174000",      # Missing hyphens
            "123e4567-e89b-12d3-a456-42661417400g",  # Invalid character 'g'
        ]

        for invalid in invalid_uuids:
            with pytest.raises(HTTPException) as exc_info:
                validate_uuid(invalid, "test_id")
            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_field_name_in_error_message(self):
        """Field name should appear in error messages"""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid("invalid", "session_id")
        assert "session_id" in exc_info.value.detail

    def test_non_string_type_rejected(self):
        """Non-string types should be rejected"""
        with pytest.raises(HTTPException) as exc_info:
            validate_uuid(12345, "test_id")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be a string" in exc_info.value.detail


class TestRateLimiting:
    """Test rate limiting for DoS prevention"""

    def test_rate_limiter_allows_within_limit(self):
        """Requests within limit should be allowed"""
        limiter = RateLimiter(max_requests=5, window_seconds=1)
        key = "test_key"

        # Make 5 requests (at limit)
        for _ in range(5):
            assert limiter.is_allowed(key) is True

    def test_rate_limiter_blocks_over_limit(self):
        """Requests over limit should be blocked"""
        limiter = RateLimiter(max_requests=3, window_seconds=1)
        key = "test_key"

        # Make 3 requests (at limit)
        for _ in range(3):
            assert limiter.is_allowed(key) is True

        # 4th request should be blocked
        assert limiter.is_allowed(key) is False

    def test_rate_limiter_resets_after_window(self):
        """Rate limit should reset after time window"""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        key = "test_key"

        # Use up limit
        assert limiter.is_allowed(key) is True
        assert limiter.is_allowed(key) is True
        assert limiter.is_allowed(key) is False

        # Wait for window to pass
        time.sleep(1.1)

        # Should allow requests again
        assert limiter.is_allowed(key) is True

    def test_rate_limiter_different_keys_independent(self):
        """Different keys should have independent rate limits"""
        limiter = RateLimiter(max_requests=2, window_seconds=1)

        # Use up limit for key1
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is False

        # key2 should still work
        assert limiter.is_allowed("key2") is True
        assert limiter.is_allowed("key2") is True

    def test_rate_limiter_get_remaining(self):
        """get_remaining should return correct count"""
        limiter = RateLimiter(max_requests=5, window_seconds=1)
        key = "test_key"

        assert limiter.get_remaining(key) == 5

        limiter.is_allowed(key)
        assert limiter.get_remaining(key) == 4

        limiter.is_allowed(key)
        limiter.is_allowed(key)
        assert limiter.get_remaining(key) == 2

    def test_rate_limiter_reset(self):
        """reset should clear rate limit for key"""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        key = "test_key"

        # Use up limit
        limiter.is_allowed(key)
        limiter.is_allowed(key)
        assert limiter.is_allowed(key) is False

        # Reset
        limiter.reset(key)

        # Should work again
        assert limiter.is_allowed(key) is True


class TestSessionOwnershipVerification:
    """Test session ownership verification for unauthorized access prevention"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return MagicMock(spec=Session)

    @pytest.fixture
    def mock_session(self):
        """Create mock test session"""
        session = MagicMock(spec=TestSession)
        session.id = str(uuid_lib.uuid4())
        session.project_id = str(uuid_lib.uuid4())
        return session

    def test_verify_session_ownership_success(self, mock_db, mock_session):
        """Valid session ownership should pass"""
        mock_db.query().filter().first.return_value = mock_session

        result = verify_session_ownership(
            session_id=mock_session.id,
            project_id=mock_session.project_id,
            db=mock_db
        )

        assert result == mock_session

    def test_verify_session_ownership_not_found(self, mock_db):
        """Non-existent session should raise 404"""
        mock_db.query().filter().first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            verify_session_ownership(
                session_id=str(uuid_lib.uuid4()),
                project_id=str(uuid_lib.uuid4()),
                db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail

    def test_verify_session_ownership_wrong_project(self, mock_db, mock_session):
        """Session from different project should raise 403"""
        mock_db.query().filter().first.return_value = mock_session
        wrong_project_id = str(uuid_lib.uuid4())

        with pytest.raises(HTTPException) as exc_info:
            verify_session_ownership(
                session_id=mock_session.id,
                project_id=wrong_project_id,
                db=mock_db
            )

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "different project" in exc_info.value.detail


class TestConnectionLeakPrevention:
    """Test database connection management for leak prevention"""

    def test_managed_session_commits_on_success(self):
        """Managed session should commit on success"""
        mock_session = MagicMock(spec=Session)

        with patch('utils.db_utils.SessionLocal', return_value=mock_session):
            from utils.db_utils import managed_db_session

            with managed_db_session() as db:
                pass  # Successful operation

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_managed_session_rolls_back_on_error(self):
        """Managed session should rollback on exception"""
        mock_session = MagicMock(spec=Session)

        with patch('utils.db_utils.SessionLocal', return_value=mock_session):
            from utils.db_utils import managed_db_session

            with pytest.raises(ValueError):
                with managed_db_session() as db:
                    raise ValueError("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()

    def test_managed_session_always_closes(self):
        """Managed session should always close connection"""
        mock_session = MagicMock(spec=Session)

        with patch('utils.db_utils.SessionLocal', return_value=mock_session):
            from utils.db_utils import managed_db_session

            # Normal case
            with managed_db_session() as db:
                pass
            assert mock_session.close.call_count == 1

            # Exception case
            try:
                with managed_db_session() as db:
                    raise ValueError("Test")
            except ValueError:
                pass
            assert mock_session.close.call_count == 2

    def test_database_session_manager_with_retry(self):
        """Database manager should retry on transient failures"""
        manager = DatabaseSessionManager()

        mock_session = MagicMock(spec=Session)
        call_count = 0

        def mock_operation(db):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Transient error")
            return "success"

        with patch('utils.db_utils.SessionLocal', return_value=mock_session):
            result = manager.execute_with_retry(mock_operation, max_retries=3)

        assert result == "success"
        assert call_count == 2  # Failed once, succeeded on second try


class TestAutoSecurityMiddleware:
    """Test automatic security middleware"""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance"""
        app = MagicMock()
        return AutoSecurityMiddleware(
            app,
            enable_uuid_validation=True,
            enable_rate_limiting=True,
            rate_limit_requests=10,
            rate_limit_window_seconds=60
        )

    def test_middleware_validates_uuid_in_path_params(self, middleware):
        """Middleware should validate UUIDs in path parameters"""
        valid_uuid = str(uuid_lib.uuid4())
        assert middleware._validate_uuid(valid_uuid, "test_id") is True

    def test_middleware_rejects_invalid_uuid(self, middleware):
        """Middleware should reject invalid UUIDs"""
        with pytest.raises(HTTPException) as exc_info:
            middleware._validate_uuid("invalid-uuid", "test_id")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_middleware_rate_limiting(self, middleware):
        """Middleware should enforce rate limits"""
        client_ip = "192.168.1.1"

        # Make requests up to limit
        for _ in range(10):
            assert middleware._check_rate_limit(client_ip) is True

        # Next request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            middleware._check_rate_limit(client_ip)
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_middleware_extracts_client_ip(self, middleware):
        """Middleware should correctly extract client IP"""
        request = MagicMock()

        # Test X-Forwarded-For
        request.headers.get.return_value = "192.168.1.1, 10.0.0.1"
        ip = middleware._extract_client_ip(request)
        assert ip == "192.168.1.1"

        # Test X-Real-IP
        request.headers.get.side_effect = lambda h: "192.168.1.2" if h == "X-Real-IP" else None
        ip = middleware._extract_client_ip(request)
        assert ip == "192.168.1.2"

    def test_middleware_exempts_health_endpoints(self, middleware):
        """Middleware should exempt health check endpoints"""
        assert middleware._is_exempt_path("/health") is True
        assert middleware._is_exempt_path("/api/monitoring/health") is True
        assert middleware._is_exempt_path("/docs") is True
        assert middleware._is_exempt_path("/api/projects") is False


class TestIntegrationSecurity:
    """Integration tests for complete security flow"""

    def test_complete_security_validation_flow(self):
        """Test complete security validation from request to database"""
        # This would require a full test setup with database
        # Placeholder for integration test
        pass

    def test_sql_injection_blocked_end_to_end(self):
        """Test that SQL injection is blocked end-to-end"""
        # Test UUID validation prevents SQL injection in actual queries
        pass

    def test_rate_limit_enforced_across_requests(self):
        """Test rate limiting works across multiple requests"""
        # Test rate limiter with actual HTTP requests
        pass

    def test_unauthorized_access_blocked_end_to_end(self):
        """Test unauthorized access is blocked end-to-end"""
        # Test session ownership with actual database
        pass


# Performance tests
class TestSecurityPerformance:
    """Test security features don't degrade performance significantly"""

    def test_uuid_validation_performance(self):
        """UUID validation should be fast"""
        valid_uuid = str(uuid_lib.uuid4())

        start = time.time()
        for _ in range(10000):
            validate_uuid(valid_uuid, "test_id")
        duration = time.time() - start

        # Should validate 10k UUIDs in less than 100ms
        assert duration < 0.1, f"UUID validation too slow: {duration}s for 10k validations"

    def test_rate_limiter_performance(self):
        """Rate limiter should be fast"""
        limiter = RateLimiter(max_requests=1000, window_seconds=60)

        start = time.time()
        for i in range(1000):
            limiter.is_allowed(f"key_{i % 10}")
        duration = time.time() - start

        # Should handle 1k checks in less than 50ms
        assert duration < 0.05, f"Rate limiting too slow: {duration}s for 1k checks"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
