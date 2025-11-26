"""
Database utility functions for safe connection management.

This module provides context managers and utilities to prevent
database connection leaks and ensure proper transaction handling.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from database import SessionLocal
import logging

logger = logging.getLogger(__name__)


@contextmanager
def managed_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic cleanup.

    Ensures:
    - Automatic commit on success
    - Automatic rollback on exception
    - Automatic connection close

    Usage:
        with managed_db_session() as db:
            result = db.query(Model).all()
            return result

    Yields:
        Session: SQLAlchemy database session

    Raises:
        Exception: Re-raises any exception after rollback
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error, rolling back transaction: {e}", exc_info=True)
        raise
    finally:
        db.close()
        logger.debug("Database session closed")


@contextmanager
def managed_db_session_no_commit() -> Generator[Session, None, None]:
    """
    Context manager for read-only database sessions.

    Does NOT automatically commit. Useful for queries that
    don't modify data. Still ensures proper cleanup.

    Usage:
        with managed_db_session_no_commit() as db:
            result = db.query(Model).all()
            return result

    Yields:
        Session: SQLAlchemy database session (read-only)
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error during read operation: {e}", exc_info=True)
        raise
    finally:
        db.close()
        logger.debug("Read-only database session closed")


def safe_commit(db: Session) -> bool:
    """
    Safely commit a database session with error handling.

    Args:
        db: SQLAlchemy session to commit

    Returns:
        bool: True if commit succeeded, False otherwise
    """
    try:
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to commit database changes: {e}", exc_info=True)
        db.rollback()
        return False


def safe_rollback(db: Session) -> None:
    """
    Safely rollback a database session with error handling.

    Args:
        db: SQLAlchemy session to rollback
    """
    try:
        db.rollback()
    except Exception as e:
        logger.error(f"Failed to rollback database transaction: {e}", exc_info=True)


def safe_close(db: Session) -> None:
    """
    Safely close a database session with error handling.

    Args:
        db: SQLAlchemy session to close
    """
    try:
        db.close()
    except Exception as e:
        logger.error(f"Failed to close database session: {e}", exc_info=True)


class DatabaseSessionManager:
    """
    Class-based database session manager for more complex scenarios.

    Usage:
        manager = DatabaseSessionManager()
        with manager.session() as db:
            result = db.query(Model).all()
            return result
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DatabaseSessionManager")

    @contextmanager
    def session(self, auto_commit: bool = True) -> Generator[Session, None, None]:
        """
        Create a managed database session.

        Args:
            auto_commit: Whether to automatically commit on success

        Yields:
            Session: SQLAlchemy database session
        """
        db = SessionLocal()
        try:
            yield db
            if auto_commit:
                db.commit()
                self.logger.debug("Transaction committed successfully")
        except Exception as e:
            db.rollback()
            self.logger.error(f"Transaction rolled back due to error: {e}", exc_info=True)
            raise
        finally:
            db.close()
            self.logger.debug("Database session closed")

    def execute_with_retry(self, func, max_retries: int = 3, *args, **kwargs):
        """
        Execute a database operation with automatic retry on transient failures.

        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            *args: Arguments to pass to function
            **kwargs: Keyword arguments to pass to function

        Returns:
            Result of the function

        Raises:
            Exception: Re-raises the last exception if all retries fail
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                with self.session() as db:
                    return func(db, *args, **kwargs)
            except Exception as e:
                last_exception = e
                self.logger.warning(
                    f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                # Don't retry certain errors
                if "IntegrityError" in str(type(e)):
                    raise

        # All retries exhausted
        self.logger.error(f"Database operation failed after {max_retries} attempts")
        raise last_exception


# Singleton instance for convenience
db_manager = DatabaseSessionManager()


# Example usage and migration patterns
"""
MIGRATION GUIDE:

1. Simple Query (BEFORE):
    from database import SessionLocal
    db = SessionLocal()
    result = db.query(Model).all()
    db.close()

   Simple Query (AFTER):
    from utils.db_utils import managed_db_session
    with managed_db_session() as db:
        result = db.query(Model).all()

2. FastAPI Endpoint (BEFORE):
    from database import SessionLocal
    @router.get("/items")
    def get_items():
        db = SessionLocal()
        items = db.query(Item).all()
        db.close()
        return items

   FastAPI Endpoint (AFTER - Recommended):
    from fastapi import Depends
    from database import get_db
    @router.get("/items")
    def get_items(db: Session = Depends(get_db)):
        items = db.query(Item).all()
        return items

3. Service Function (BEFORE):
    class MyService:
        def process(self):
            db = SessionLocal()
            try:
                result = db.query(Model).all()
                db.commit()
                return result
            except:
                db.rollback()
                raise
            finally:
                db.close()

   Service Function (AFTER):
    from utils.db_utils import managed_db_session
    class MyService:
        def process(self):
            with managed_db_session() as db:
                result = db.query(Model).all()
                return result

4. Complex Transaction (BEFORE):
    db = SessionLocal()
    try:
        item1 = db.query(Model1).first()
        item2 = Model2(data=item1.value)
        db.add(item2)
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()

   Complex Transaction (AFTER):
    from utils.db_utils import db_manager
    def complex_operation(db):
        item1 = db.query(Model1).first()
        item2 = Model2(data=item1.value)
        db.add(item2)
        return item2

    result = db_manager.execute_with_retry(complex_operation)
"""
