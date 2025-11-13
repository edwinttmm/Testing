"""
Pytest Configuration and Shared Fixtures for Ground Truth Tests

Provides:
- Database setup/teardown
- Benchmark configuration
- Performance test helpers
- Mock factories
"""

import pytest
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from database import Base
from models import Project, Video, TestSession, GroundTruthObject


# ===== DATABASE SETUP =====

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine with in-memory SQLite"""
    # Use in-memory SQLite for fast tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL debugging
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create isolated database session for each test"""
    connection = test_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    # Rollback transaction after test
    session.close()
    transaction.rollback()
    connection.close()
