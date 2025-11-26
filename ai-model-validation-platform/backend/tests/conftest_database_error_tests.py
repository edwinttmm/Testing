"""
Pytest Configuration for Database Error Tests

Shared fixtures and configuration for database error testing suite.
"""

from typing import Any
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Generator, Callable
import logging


# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Shared Fixtures

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_session_factory():
    """Factory to create mock database sessions."""
    sessions_created = []

    def create_session():
        session = MagicMock(spec=Session)
        session.session_id = id(session)
        session.is_active = True
        session.close = Mock()
        session.rollback = Mock()
        session.commit = Mock()
        session.execute = Mock()
        session.query = Mock()

        sessions_created.append(session)
        return session

    create_session.sessions_created = sessions_created
    return create_session


@pytest.fixture
def error_injection():
    """Helper to inject errors into mock sessions."""
    class ErrorInjector:
        @staticmethod
        def inject_connection_error(session):
            from sqlalchemy.exc import OperationalError
            session.execute.side_effect = OperationalError(
                statement="SELECT 1",
                params={},
                orig=Exception("Connection refused")
            )

        @staticmethod
        def inject_timeout_error(session):
            from sqlalchemy.exc import TimeoutError as SQLTimeoutError
            session.execute.side_effect = SQLTimeoutError(
                statement="SELECT * FROM table",
                params={},
                orig=Exception("Query timeout")
            )

        @staticmethod
        def inject_integrity_error(session):
            from sqlalchemy.exc import IntegrityError
            session.execute.side_effect = IntegrityError(
                statement="INSERT INTO table",
                params={},
                orig=Exception("UNIQUE constraint failed")
            )

        @staticmethod
        def inject_lock_error(session):
            from sqlalchemy.exc import OperationalError
            session.execute.side_effect = OperationalError(
                statement="UPDATE table",
                params={},
                orig=Exception("Deadlock detected")
            )

        @staticmethod
        def inject_cleanup_error(session):
            session.close.side_effect = RuntimeError("Error during cleanup")

    return ErrorInjector()


@pytest.fixture
def session_tracker():
    """Track session lifecycle for testing."""
    class SessionTracker:
        def __init__(self):
            self.created = []
            self.closed = []
            self.active = []
            self.errors = []

        def track_create(self, session):
            self.created.append(session.session_id)
            self.active.append(session.session_id)

        def track_close(self, session):
            if session.session_id in self.active:
                self.active.remove(session.session_id)
            self.closed.append(session.session_id)

        def track_error(self, error, context=None):
            self.errors.append({
                "error": str(error),
                "type": type(error).__name__,
                "context": context
            })

        def get_leak_count(self):
            return len(self.active)

        def reset(self):
            self.created.clear()
            self.closed.clear()
            self.active.clear()
            self.errors.clear()

    tracker = SessionTracker()
    yield tracker
    tracker.reset()


@pytest.fixture
def db_session_generator(mock_session_factory, session_tracker):
    """Create a database session generator for testing."""
    def generator():
        session = mock_session_factory()
        session_tracker.track_create(session)

        # Override close to track
        original_close = session.close

        def tracked_close():
            session_tracker.track_close(session)
            return original_close()

        session.close = Mock(side_effect=tracked_close)

        try:
            yield session
        finally:
            try:
                session.close()
            except Exception as e:
                session_tracker.track_error(e, "cleanup")

    return generator


@pytest.fixture
def performance_timer():
    """Timer for performance measurements."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        def elapsed(self):
            if self.start_time is None or self.end_time is None:
                return None
            return self.end_time - self.start_time

        def __enter__(self):
            self.start()
            return self

        def __exit__(self, *args):
            self.stop()

    return Timer


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks after each test."""
    yield
    # Cleanup happens automatically with pytest


# Markers for test organization

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "stress: marks tests as stress/performance tests"
    )
    config.addinivalue_line(
        "markers", "async: marks tests as async tests"
    )


# Helper functions

def assert_session_cleanup(session_tracker, expected_count=None):
    """Assert that sessions were properly cleaned up."""
    leak_count = session_tracker.get_leak_count()

    if expected_count is not None:
        assert len(session_tracker.created) == expected_count, \
            f"Expected {expected_count} sessions, got {len(session_tracker.created)}"

    assert leak_count == 0, \
        f"Session leak detected: {leak_count} sessions not cleaned up"

    assert len(session_tracker.closed) == len(session_tracker.created), \
        "Not all sessions were closed"


def create_test_app_with_db(db_dependency):
    """Create a test FastAPI app with database dependency."""
    from fastapi import FastAPI, Depends

    app = FastAPI()

    @app.get("/test")
    def test_endpoint(db: Session = Depends(db_dependency)):
        return {"status": "ok"}

    @app.get("/test-error")
    def error_endpoint(db: Session = Depends(db_dependency)):
        raise ValueError("Test error")

    return app


# Test data generators

@pytest.fixture
def test_data_generator():
    """Generate test data for database operations."""
    class DataGenerator:
        @staticmethod
        def user_data(count=1):
            return [
                {"id": i, "name": f"User {i}", "email": f"user{i}@test.com"}
                for i in range(count)
            ]

        @staticmethod
        def large_dataset(size_mb=1):
            # Generate approximately size_mb of data
            record_size = 1024  # 1KB per record
            num_records = size_mb * 1024
            return ["x" * record_size for _ in range(num_records)]

    return DataGenerator()


# Cleanup hooks

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Ensure cleanup after each test."""
    yield
    # Any global cleanup can go here
    import gc
    gc.collect()
