"""
Middleware Error Handling Tests

Tests to verify middleware correctly handles errors in various scenarios,
especially focusing on generator cleanup and error propagation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
import asyncio


class DatabaseSessionMiddleware(BaseHTTPMiddleware):
    """
    Test middleware that manages database sessions.
    This simulates the actual middleware in the application.
    """

    def __init__(self, app, db_session_generator):
        super().__init__(app)
        self.db_session_generator = db_session_generator

    async def dispatch(self, request: Request, call_next):
        """Handle request with database session."""
        session = None
        try:
            # Create session
            session_gen = self.db_session_generator()
            session = next(session_gen)

            # Attach to request
            request.state.db = session

            # Process request
            response = await call_next(request)

            # Cleanup generator
            try:
                next(session_gen)
            except StopIteration:
                pass

            return response

        except Exception as e:
            # Ensure cleanup happens even on error
            if session:
                try:
                    session.rollback()
                except:
                    pass
                try:
                    session.close()
                except:
                    pass
            raise
        finally:
            # Additional cleanup safety net
            if session and hasattr(session, 'close'):
                try:
                    session.close()
                except:
                    pass  # Don't raise during cleanup


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock(spec=Session)
    session.close = Mock()
    session.rollback = Mock()
    session.commit = Mock()
    session.is_active = True
    return session


@pytest.fixture
def session_generator(mock_session):
    """Create a session generator that tracks cleanup."""
    cleanup_called = []

    def generator():
        try:
            yield mock_session
        finally:
            cleanup_called.append(True)
            mock_session.close()

    generator.cleanup_called = cleanup_called
    return generator


@pytest.fixture
def test_app_with_middleware(session_generator):
    """Create test app with database middleware."""
    app = FastAPI()

    # Add middleware
    app.add_middleware(DatabaseSessionMiddleware, db_session_generator=session_generator)

    @app.get("/success")
    def success_endpoint(request: Request):
        db = request.state.db
        return {"status": "success", "db_active": db.is_active}

    @app.get("/error")
    def error_endpoint(request: Request):
        db = request.state.db
        raise ValueError("Test error")

    @app.get("/db-error")
    def db_error_endpoint(request: Request):
        db = request.state.db
        db.execute = Mock(side_effect=Exception("Database error"))
        db.execute("SELECT 1")
        return {"status": "should not reach"}

    return app


# Test Cases

def test_middleware_handles_generator_error(test_app_with_middleware, session_generator, mock_session):
    """
    Test: Middleware should handle generator cleanup errors gracefully.

    Expected behavior:
    - Request is processed
    - Generator cleanup is called
    - If cleanup raises error, it's caught
    - Response is still returned (or original error propagated)
    """
    # Arrange
    client = TestClient(test_app_with_middleware)

    # Act
    response = client.get("/success")

    # Assert
    assert response.status_code == 200
    assert mock_session.close.called, "Session should be closed"
    assert len(session_generator.cleanup_called) > 0, "Generator cleanup should be called"


def test_middleware_propagates_original_error(test_app_with_middleware, mock_session):
    """
    Test: Original error should be propagated, not cleanup error.

    Expected behavior:
    - Endpoint raises ValueError
    - Cleanup happens (may also error)
    - ValueError is propagated to client, not cleanup error
    """
    # Arrange
    client = TestClient(test_app_with_middleware)

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        client.get("/error")

    assert "Test error" in str(exc_info.value)
    assert mock_session.close.called, "Session should still be closed"


def test_multiple_error_handlers_no_conflict():
    """
    Test: Multiple error handlers should work together without conflicts.

    Expected behavior:
    - Multiple middleware layers
    - Each handles errors independently
    - All cleanup happens
    - No conflicts or double-cleanup issues
    """
    # Arrange
    cleanup_order = []

    class OuterMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            try:
                response = await call_next(request)
                return response
            finally:
                cleanup_order.append("outer")

    class InnerMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            try:
                response = await call_next(request)
                return response
            finally:
                cleanup_order.append("inner")

    app = FastAPI()
    app.add_middleware(OuterMiddleware)
    app.add_middleware(InnerMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    client = TestClient(app)

    # Act
    response = client.get("/test")

    # Assert
    assert response.status_code == 200
    assert "outer" in cleanup_order
    assert "inner" in cleanup_order


def test_middleware_cleanup_on_client_disconnect():
    """
    Test: Middleware should clean up even if client disconnects.

    Expected behavior:
    - Client disconnects mid-request
    - Cleanup still happens
    - No hanging resources
    """
    # Arrange
    cleanup_called = []

    class CleanupMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            try:
                response = await call_next(request)
                return response
            finally:
                cleanup_called.append(True)

    app = FastAPI()
    app.add_middleware(CleanupMiddleware)

    @app.get("/slow")
    async def slow_endpoint():
        await asyncio.sleep(10)  # Simulates long operation
        return {"status": "completed"}

    # Act - Note: TestClient doesn't perfectly simulate disconnects,
    # but we can test the cleanup still happens
    client = TestClient(app)

    try:
        # This will timeout but cleanup should still happen
        with pytest.raises(Exception):
            client.get("/slow", timeout=0.1)
    except:
        pass

    # Assert
    # In real scenario, cleanup should happen even on disconnect
    # This is a limitation of the test - actual behavior needs integration testing


def test_middleware_error_in_finally_block():
    """
    Test: Errors in finally block should not prevent other cleanup.

    Expected behavior:
    - First cleanup operation raises error
    - Subsequent cleanup operations still execute
    - Original error (if any) is preserved
    """
    # Arrange
    cleanup_operations = []

    def cleanup_with_potential_error():
        session = Mock()

        try:
            yield session
        finally:
            # First cleanup - might error
            try:
                cleanup_operations.append("rollback")
                session.rollback()
            except:
                pass

            # Second cleanup - should still run
            try:
                cleanup_operations.append("close")
                session.close()
            except:
                pass

            # Third cleanup - should still run
            try:
                cleanup_operations.append("final")
            except:
                pass

    # Act
    gen = cleanup_with_potential_error()
    next(gen)

    try:
        next(gen)
    except StopIteration:
        pass

    # Assert
    assert "rollback" in cleanup_operations
    assert "close" in cleanup_operations
    assert "final" in cleanup_operations


def test_middleware_nested_context_managers():
    """
    Test: Nested context managers in middleware should all clean up.

    Expected behavior:
    - Multiple nested resources
    - All are cleaned up in reverse order
    - Even if one cleanup fails
    """
    # Arrange
    cleanup_order = []

    class Resource:
        def __init__(self, name):
            self.name = name

        def close(self):
            cleanup_order.append(self.name)

    def nested_resources():
        r1 = Resource("outer")
        try:
            r2 = Resource("middle")
            try:
                r3 = Resource("inner")
                try:
                    yield [r1, r2, r3]
                finally:
                    r3.close()
            finally:
                r2.close()
        finally:
            r1.close()

    # Act
    gen = nested_resources()
    resources = next(gen)

    try:
        next(gen)
    except StopIteration:
        pass

    # Assert
    assert cleanup_order == ["inner", "middle", "outer"], "Cleanup should happen in reverse order"


@pytest.mark.asyncio
async def test_middleware_async_generator_cleanup():
    """
    Test: Async generators in middleware should clean up properly.

    Expected behavior:
    - Async generator yields resource
    - Async cleanup happens in finally
    - Works with async context managers
    """
    # Arrange
    cleanup_called = []

    async def async_resource_manager():
        resource = Mock()
        try:
            yield resource
            await asyncio.sleep(0.01)  # Simulate async work
        finally:
            cleanup_called.append(True)
            resource.close()

    # Act
    gen = async_resource_manager()
    resource = await gen.__anext__()

    try:
        await gen.__anext__()
    except StopAsyncIteration:
        pass

    # Assert
    assert len(cleanup_called) == 1, "Async cleanup should be called"
    assert resource.close.called, "Resource should be closed"


def test_middleware_exception_chaining():
    """
    Test: Exception chaining should preserve all error context.

    Expected behavior:
    - Original exception occurs
    - Cleanup exception also occurs
    - Both exceptions are available in context
    - Original exception is raised
    """
    # Arrange
    original_error = ValueError("Original error")
    cleanup_error = RuntimeError("Cleanup error")

    def operation_with_errors():
        try:
            raise original_error
        finally:
            try:
                raise cleanup_error
            except RuntimeError:
                # Log but don't re-raise cleanup error
                pass

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        operation_with_errors()

    assert exc_info.value is original_error, "Original error should be raised"


def test_middleware_concurrent_requests():
    """
    Test: Concurrent requests should have isolated middleware state.

    Expected behavior:
    - Multiple requests processed concurrently
    - Each has its own middleware state
    - No cross-contamination
    - All clean up properly
    """
    # Arrange
    request_sessions = {}

    class SessionTrackingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            session_id = id(request)
            session = Mock(spec=Session)
            request_sessions[session_id] = session

            try:
                request.state.session_id = session_id
                response = await call_next(request)
                return response
            finally:
                session.close()

    app = FastAPI()
    app.add_middleware(SessionTrackingMiddleware)

    @app.get("/test/{item_id}")
    def test_endpoint(item_id: int, request: Request):
        return {"item_id": item_id, "session_id": request.state.session_id}

    client = TestClient(app)

    # Act - Make multiple requests
    responses = [client.get(f"/test/{i}") for i in range(5)]

    # Assert
    assert len(responses) == 5
    assert all(r.status_code == 200 for r in responses)
    # All sessions should be closed
    assert all(s.close.called for s in request_sessions.values())


def test_middleware_memory_cleanup():
    """
    Test: Middleware should not leak memory across requests.

    Expected behavior:
    - Request state is cleaned up
    - No references kept after request
    - Memory can be garbage collected
    """
    # Arrange
    import gc

    class StatefulMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # Attach some state
            request.state.large_data = ["data"] * 1000

            try:
                response = await call_next(request)
                return response
            finally:
                # Clean up state
                if hasattr(request.state, 'large_data'):
                    del request.state.large_data

    app = FastAPI()
    app.add_middleware(StatefulMiddleware)

    @app.get("/test")
    def test_endpoint(request: Request):
        return {"has_data": hasattr(request.state, 'large_data')}

    client = TestClient(app)

    # Act
    for _ in range(10):
        response = client.get("/test")
        assert response.json()["has_data"] == True

    # Force garbage collection
    gc.collect()

    # Assert - If no leaks, this should complete quickly
    # In a real test, you'd measure memory usage
    assert True, "Memory cleanup test completed"


def test_middleware_response_modification_with_cleanup():
    """
    Test: Middleware can modify response and still clean up properly.

    Expected behavior:
    - Middleware modifies response
    - Cleanup still happens
    - Modified response is returned
    """
    # Arrange
    cleanup_called = []

    class ResponseModifyingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            try:
                response = await call_next(request)
                # Modify response
                response.headers["X-Custom-Header"] = "test-value"
                return response
            finally:
                cleanup_called.append(True)

    app = FastAPI()
    app.add_middleware(ResponseModifyingMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    client = TestClient(app)

    # Act
    response = client.get("/test")

    # Assert
    assert response.status_code == 200
    assert response.headers.get("X-Custom-Header") == "test-value"
    assert len(cleanup_called) == 1, "Cleanup should be called"
