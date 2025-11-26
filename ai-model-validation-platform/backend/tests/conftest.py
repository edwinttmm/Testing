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
import uuid
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import create_engine, event, select, delete, update, func
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

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
def test_db(test_engine) -> Generator[Session, None, None]:
    """Create isolated database session for each test (original fixture name)"""
    connection = test_engine.connect()
    transaction = connection.begin()

    # Create session factory bound to connection
    SessionLocal = sessionmaker(bind=connection, expire_on_commit=False)
    session = SessionLocal()

    try:
        yield session
        # Commit any pending changes
        session.commit()
    except Exception:
        # Rollback on error
        session.rollback()
        raise
    finally:
        # Always close session and rollback transaction
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create isolated database session for each test (alias for test_db)"""
    connection = test_engine.connect()
    transaction = connection.begin()

    # Create session factory bound to connection with proper settings
    SessionLocal = sessionmaker(
        bind=connection,
        expire_on_commit=False,  # Prevent detached instance errors
        autoflush=False  # Give tests more control
    )
    session = SessionLocal()

    try:
        yield session
        # Commit any pending changes
        session.commit()
    except Exception:
        # Rollback on error
        session.rollback()
        raise
    finally:
        # Expunge all objects to prevent session errors
        session.expunge_all()
        # Close session and rollback transaction
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def sample_project_id(db_session) -> str:
    """Create a sample project and return its ID"""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project",
        description="Test project for integration tests",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        lens_type="Standard",
        resolution="640x480",
        frame_rate=30,
        signal_type="GPIO",
        status="active",
        owner_id="test_user"
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return project.id


@pytest.fixture(scope="function")
def sample_project(db_session) -> Project:
    """Create and return a sample project object"""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project",
        description="Test project for integration tests",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        lens_type="Standard",
        resolution="640x480",
        frame_rate=30,
        signal_type="GPIO",
        status="active",
        owner_id="test_user"
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return project


@pytest.fixture(scope="function")
def client():
    """Create FastAPI test client"""
    from main import app
    return TestClient(app)
