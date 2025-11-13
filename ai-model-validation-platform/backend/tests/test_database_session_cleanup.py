"""
Test database session cleanup to verify fix for RuntimeError: generator didn't stop after throw()

This test ensures that database sessions are properly cleaned up even when exceptions occur.
"""

import pytest
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_db, SessionLocal


class TestDatabaseSessionCleanup:
    """Test that database sessions are properly cleaned up in all scenarios"""

    def test_normal_session_cleanup(self):
        """Test that sessions are properly closed in normal flow"""
        gen = get_db()
        db = next(gen)

        # Verify we got a session
        assert db is not None

        # Close the generator normally
        try:
            next(gen)
        except StopIteration:
            pass  # Expected

        # Verify session was closed
        assert not db.is_active

    def test_session_cleanup_on_exception(self):
        """Test that sessions are properly closed when exception occurs"""
        gen = get_db()
        db = next(gen)

        # Simulate an exception during request processing
        try:
            gen.throw(ValueError("Test exception"))
        except ValueError:
            pass  # Expected
        except RuntimeError as e:
            if "generator didn't stop" in str(e):
                pytest.fail(f"Generator cleanup failed: {e}")

        # Verify session was still closed despite exception
        assert not db.is_active

    def test_session_cleanup_on_sqlalchemy_error(self):
        """Test that sessions are cleaned up when SQLAlchemy errors occur"""
        gen = get_db()
        db = next(gen)

        # Simulate a SQLAlchemy error
        try:
            gen.throw(SQLAlchemyError("Test SQL error"))
        except SQLAlchemyError:
            pass  # Expected
        except RuntimeError as e:
            if "generator didn't stop" in str(e):
                pytest.fail(f"Generator cleanup failed on SQLAlchemyError: {e}")

        # Verify session was closed
        assert not db.is_active

    def test_session_cleanup_on_operational_error(self):
        """Test that sessions are cleaned up when operational errors occur"""
        gen = get_db()
        db = next(gen)

        # Simulate an operational error
        try:
            gen.throw(OperationalError("Test", None, None))
        except OperationalError:
            pass  # Expected
        except RuntimeError as e:
            if "generator didn't stop" in str(e):
                pytest.fail(f"Generator cleanup failed on OperationalError: {e}")

        # Verify session was closed
        assert not db.is_active

    def test_rollback_error_suppressed(self):
        """Test that errors during rollback are suppressed and don't cause generator issues"""
        with patch.object(SessionLocal, 'rollback', side_effect=Exception("Rollback failed")):
            gen = get_db()
            db = next(gen)

            # Throw an exception that would trigger rollback
            try:
                gen.throw(SQLAlchemyError("Test error"))
            except SQLAlchemyError:
                pass  # Expected - the original error should be raised
            except RuntimeError as e:
                if "generator didn't stop" in str(e):
                    pytest.fail(f"Generator failed when rollback raised exception: {e}")
            except Exception as e:
                if "Rollback failed" in str(e):
                    pytest.fail(f"Rollback error was not suppressed: {e}")

    def test_close_error_suppressed(self):
        """Test that errors during close are suppressed and logged"""
        gen = get_db()
        db = next(gen)

        # Mock close to raise an exception
        original_close = db.close
        db.close = Mock(side_effect=Exception("Close failed"))

        # Close the generator
        try:
            next(gen)
        except StopIteration:
            pass  # Expected
        except RuntimeError as e:
            if "generator didn't stop" in str(e):
                pytest.fail(f"Generator failed when close raised exception: {e}")
        except Exception as e:
            if "Close failed" in str(e):
                pytest.fail(f"Close error was not suppressed: {e}")

    def test_multiple_exception_scenarios(self):
        """Test that generator cleanup works with multiple exception types"""
        exception_types = [
            ValueError("Test ValueError"),
            KeyError("Test KeyError"),
            AttributeError("Test AttributeError"),
            RuntimeError("Test RuntimeError (not generator)"),
        ]

        for exc in exception_types:
            gen = get_db()
            db = next(gen)

            try:
                gen.throw(type(exc), exc)
            except type(exc):
                pass  # Expected
            except RuntimeError as e:
                if "generator didn't stop" in str(e):
                    pytest.fail(f"Generator cleanup failed for {type(exc).__name__}: {e}")

            # Verify session was closed
            assert not db.is_active, f"Session not closed after {type(exc).__name__}"

    @patch('database.USE_UNIFIED_DATABASE', True)
    @patch('database.get_database_manager')
    def test_unified_database_session_cleanup(self, mock_get_manager):
        """Test that unified database sessions are also properly cleaned up"""
        mock_manager = Mock()
        mock_session = Mock()
        mock_session.execute = Mock()
        mock_session.rollback = Mock()
        mock_session.close = Mock()
        mock_session.is_active = False

        mock_manager.get_session.return_value = mock_session
        mock_get_manager.return_value = mock_manager

        gen = get_db()
        db = next(gen)

        # Verify we got the unified session
        assert db == mock_session

        # Throw an exception
        try:
            gen.throw(ValueError("Test exception"))
        except ValueError:
            pass  # Expected
        except RuntimeError as e:
            if "generator didn't stop" in str(e):
                pytest.fail(f"Unified database generator cleanup failed: {e}")

        # Verify session was closed
        mock_session.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
