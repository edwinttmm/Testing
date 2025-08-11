# Test Automation Framework - AI Model Validation Platform

## Framework Architecture Overview

The test automation framework for the AI Model Validation Platform is designed to provide comprehensive, maintainable, and scalable testing across all system components. The framework supports multiple test types, environments, and execution strategies while maintaining clear separation of concerns.

## Technology Stack

### Backend Testing Stack
- **pytest** - Primary testing framework
- **pytest-asyncio** - Async/await test support
- **pytest-cov** - Code coverage reporting
- **pytest-xdist** - Parallel test execution
- **pytest-mock** - Enhanced mocking capabilities
- **fastapi.testclient** - API endpoint testing
- **sqlalchemy-utils** - Database testing utilities
- **factory-boy** - Test data generation
- **faker** - Realistic fake data generation
- **locust** - Load and performance testing

### Frontend Testing Stack
- **Jest** - JavaScript testing framework
- **React Testing Library** - React component testing
- **MSW (Mock Service Worker)** - API mocking
- **Playwright** - End-to-end browser testing
- **Storybook** - Component documentation and testing
- **Jest-coverage** - Frontend code coverage

### Cross-Platform Tools
- **Docker** - Containerized test environments
- **Docker Compose** - Multi-service test orchestration
- **GitHub Actions** - CI/CD pipeline automation
- **Allure** - Test reporting and analytics
- **SonarQube** - Code quality analysis

## Framework Structure

```
tests/
├── conftest.py                 # Global pytest configuration
├── pytest.ini                 # Pytest settings
├── requirements-test.txt       # Test dependencies
├── fixtures/                   # Test data and files
│   ├── videos/                # Sample video files
│   ├── images/                # Test images
│   └── data/                  # JSON test data
├── unit/                      # Unit tests
│   ├── backend/               # Backend unit tests
│   └── frontend/              # Frontend unit tests
├── integration/               # Integration tests
│   ├── api/                   # API integration tests
│   ├── database/              # Database integration tests
│   └── websocket/             # WebSocket tests
├── e2e/                       # End-to-end tests
│   ├── ui/                    # Browser-based E2E tests
│   ├── performance/           # Performance tests
│   └── workflows/             # Complete user workflows
├── utils/                     # Test utilities
│   ├── factories.py           # Test data factories
│   ├── helpers.py             # Common test helpers
│   └── mock_services.py       # Service mocks
├── reports/                   # Test reports
│   ├── coverage/              # Coverage reports
│   ├── junit/                 # JUnit XML reports
│   └── allure/                # Allure reports
└── documentation/             # Test documentation
    ├── test_strategy.md
    ├── unit_test_specs.md
    └── integration_test_specs.md
```

## Core Testing Utilities

### Test Data Factories

```python
# tests/utils/factories.py

import factory
from factory import fuzzy
from faker import Faker
from datetime import datetime, timezone
import uuid

from models import User, Project, Video, TestSession, DetectionEvent

fake = Faker()

class UserFactory(factory.Factory):
    """Factory for creating test users."""
    class Meta:
        model = User
    
    id = factory.LazyFunction(uuid.uuid4)
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    hashed_password = factory.LazyFunction(
        lambda: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj8Bk2/x"
    )
    full_name = factory.LazyAttribute(lambda obj: fake.name())
    is_active = True
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))

class ProjectFactory(factory.Factory):
    """Factory for creating test projects."""
    class Meta:
        model = Project
    
    id = factory.LazyFunction(uuid.uuid4)
    name = factory.LazyAttribute(lambda obj: f"Test Project {fake.word()}")
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    camera_model = fuzzy.FuzzyChoice([
        "FLIR Blackfly S", "Basler acA1920", "Allied Vision Mako", "Point Grey Grasshopper"
    ])
    camera_view = fuzzy.FuzzyChoice([
        "Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"
    ])
    lens_type = fuzzy.FuzzyChoice(["Wide-angle", "Telephoto", "Standard", "Fish-eye"])
    resolution = fuzzy.FuzzyChoice(["1920x1080", "2592x1944", "1280x720", "3840x2160"])
    frame_rate = fuzzy.FuzzyChoice([15, 30, 60, 120])
    signal_type = fuzzy.FuzzyChoice(["GPIO", "Network Packet", "Serial"])
    status = fuzzy.FuzzyChoice(["Active", "Completed", "Draft"])
    owner_id = factory.SubFactory(UserFactory)
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))

class VideoFactory(factory.Factory):
    """Factory for creating test videos."""
    class Meta:
        model = Video
    
    id = factory.LazyFunction(uuid.uuid4)
    filename = factory.LazyAttribute(lambda obj: f"test_video_{fake.uuid4()}.mp4")
    file_path = factory.LazyAttribute(
        lambda obj: f"/uploads/videos/{obj.filename}"
    )
    file_size = fuzzy.FuzzyInteger(1000000, 100000000)  # 1MB to 100MB
    duration = fuzzy.FuzzyFloat(10.0, 300.0)  # 10s to 5min
    fps = fuzzy.FuzzyChoice([15.0, 24.0, 30.0, 60.0])
    resolution = "1920x1080"
    status = fuzzy.FuzzyChoice(["uploaded", "processing", "completed", "failed"])
    ground_truth_generated = False
    project_id = factory.SubFactory(ProjectFactory)
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))

class TestSessionFactory(factory.Factory):
    """Factory for creating test sessions."""
    class Meta:
        model = TestSession
    
    id = factory.LazyFunction(uuid.uuid4)
    name = factory.LazyAttribute(lambda obj: f"Test Session {fake.word()}")
    project_id = factory.SubFactory(ProjectFactory)
    video_id = factory.SubFactory(VideoFactory)
    tolerance_ms = fuzzy.FuzzyInteger(50, 500)
    status = fuzzy.FuzzyChoice(["created", "running", "completed", "failed"])
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))

class DetectionEventFactory(factory.Factory):
    """Factory for creating detection events."""
    class Meta:
        model = DetectionEvent
    
    id = factory.LazyFunction(uuid.uuid4)
    test_session_id = factory.SubFactory(TestSessionFactory)
    timestamp = fuzzy.FuzzyFloat(0.0, 300.0)
    confidence = fuzzy.FuzzyFloat(0.1, 1.0)
    class_label = fuzzy.FuzzyChoice(["pedestrian", "cyclist", "vehicle", "distracted_driver"])
    validation_result = fuzzy.FuzzyChoice(["TP", "FP", "FN"])
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
```

### Database Test Utilities

```python
# tests/utils/database_helpers.py

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from models import Base

class DatabaseTestHelper:
    """Helper class for database testing operations."""
    
    def __init__(self, database_url=None):
        self.database_url = database_url or "sqlite:///:memory:"
        self.engine = None
        self.session_factory = None
        self._setup_engine()
    
    def _setup_engine(self):
        """Setup test database engine with proper configuration."""
        self.engine = create_engine(
            self.database_url,
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False  # For SQLite
            } if "sqlite" in self.database_url else {},
            echo=False  # Set to True for SQL debugging
        )
        
        # Enable foreign key constraints for SQLite
        if "sqlite" in self.database_url:
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        
        self.session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def create_all_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_all_tables(self):
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)
    
    def get_session(self):
        """Get a database session for testing."""
        return self.session_factory()
    
    def cleanup_session(self, session):
        """Clean up database session."""
        session.rollback()
        session.close()
    
    def truncate_all_tables(self, session):
        """Truncate all tables for clean test state."""
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()

# Global test database helper
test_db_helper = DatabaseTestHelper()

@pytest.fixture(scope="session")
def test_database():
    """Session-scoped test database fixture."""
    test_db_helper.create_all_tables()
    yield test_db_helper
    test_db_helper.drop_all_tables()

@pytest.fixture
def test_db_session(test_database):
    """Function-scoped database session fixture."""
    session = test_database.get_session()
    try:
        yield session
    finally:
        test_database.cleanup_session(session)
        test_database.truncate_all_tables(session)
```

### API Test Client

```python
# tests/utils/api_client.py

from fastapi.testclient import TestClient
from typing import Dict, Any, Optional
import json
from main import app

class TestAPIClient:
    """Enhanced test client for API testing."""
    
    def __init__(self, base_url: str = "http://testserver"):
        self.client = TestClient(app, base_url=base_url)
        self.auth_token = None
        self.default_headers = {
            "Content-Type": "application/json"
        }
    
    def set_auth_token(self, token: str):
        """Set authentication token for requests."""
        self.auth_token = token
        self.default_headers["Authorization"] = f"Bearer {token}"
    
    def clear_auth(self):
        """Clear authentication token."""
        self.auth_token = None
        if "Authorization" in self.default_headers:
            del self.default_headers["Authorization"]
    
    def get(self, url: str, params: Optional[Dict] = None, **kwargs):
        """Enhanced GET request with automatic auth headers."""
        headers = kwargs.pop("headers", {})
        headers.update(self.default_headers)
        return self.client.get(url, params=params, headers=headers, **kwargs)
    
    def post(self, url: str, data: Any = None, json_data: Any = None, **kwargs):
        """Enhanced POST request with automatic auth headers."""
        headers = kwargs.pop("headers", {})
        headers.update(self.default_headers)
        
        if json_data is not None:
            return self.client.post(url, json=json_data, headers=headers, **kwargs)
        return self.client.post(url, data=data, headers=headers, **kwargs)
    
    def put(self, url: str, data: Any = None, json_data: Any = None, **kwargs):
        """Enhanced PUT request with automatic auth headers."""
        headers = kwargs.pop("headers", {})
        headers.update(self.default_headers)
        
        if json_data is not None:
            return self.client.put(url, json=json_data, headers=headers, **kwargs)
        return self.client.put(url, data=data, headers=headers, **kwargs)
    
    def delete(self, url: str, **kwargs):
        """Enhanced DELETE request with automatic auth headers."""
        headers = kwargs.pop("headers", {})
        headers.update(self.default_headers)
        return self.client.delete(url, headers=headers, **kwargs)
    
    def upload_file(self, url: str, file_path: str, field_name: str = "file", **kwargs):
        """Upload file with multipart form data."""
        headers = kwargs.pop("headers", {})
        # Don't set Content-Type for multipart uploads
        auth_headers = {k: v for k, v in self.default_headers.items() 
                       if k != "Content-Type"}
        headers.update(auth_headers)
        
        with open(file_path, "rb") as file:
            files = {field_name: file}
            return self.client.post(url, files=files, headers=headers, **kwargs)
    
    def authenticate_user(self, email: str, password: str) -> Dict:
        """Authenticate user and set token automatically."""
        response = self.post("/auth/login", json_data={
            "email": email,
            "password": password
        })
        
        if response.status_code == 200:
            token_data = response.json()
            self.set_auth_token(token_data["access_token"])
            return token_data
        
        raise Exception(f"Authentication failed: {response.status_code}")

@pytest.fixture
def api_client():
    """Test API client fixture."""
    return TestAPIClient()

@pytest.fixture
def authenticated_api_client(api_client, test_user):
    """Pre-authenticated API client fixture."""
    api_client.authenticate_user(test_user.email, "testpassword")
    return api_client
```

### Mock Services

```python
# tests/utils/mock_services.py

from unittest.mock import MagicMock, AsyncMock
import numpy as np
from typing import List, Dict, Any

class MockGroundTruthService:
    """Mock ground truth service for testing."""
    
    def __init__(self):
        self.processed_videos = {}
        self.ground_truth_data = {}
    
    def process_video_async(self, video_id: str, video_file):
        """Mock async video processing."""
        # Simulate processing time
        self.processed_videos[video_id] = {
            "status": "processing",
            "progress": 0
        }
        
        # Simulate completion
        self.processed_videos[video_id] = {
            "status": "completed", 
            "progress": 100
        }
        
        # Generate mock ground truth
        self.ground_truth_data[video_id] = [
            {
                "timestamp": 10.5,
                "class_label": "pedestrian",
                "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 100},
                "confidence": 0.95
            },
            {
                "timestamp": 25.2,
                "class_label": "cyclist",
                "bounding_box": {"x": 300, "y": 150, "width": 60, "height": 80},
                "confidence": 0.88
            }
        ]
    
    def get_ground_truth(self, video_id: str):
        """Mock ground truth retrieval."""
        return self.ground_truth_data.get(video_id)
    
    def get_processing_status(self, video_id: str):
        """Mock processing status check."""
        return self.processed_videos.get(video_id, {"status": "not_found"})

class MockRaspberryPiService:
    """Mock Raspberry Pi service for testing."""
    
    def __init__(self):
        self.connected = False
        self.detection_events = []
        self.system_status = {
            "temperature": 45.2,
            "cpu_usage": 25.6,
            "memory_usage": 512,
            "disk_usage": 75.3
        }
    
    def connect(self) -> bool:
        """Mock Pi connection."""
        self.connected = True
        return True
    
    def disconnect(self):
        """Mock Pi disconnection."""
        self.connected = False
    
    def is_connected(self) -> bool:
        """Mock connection status."""
        return self.connected
    
    def capture_frame(self) -> np.ndarray:
        """Mock frame capture."""
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    def send_detection_event(self, event: Dict[str, Any]):
        """Mock sending detection event."""
        self.detection_events.append(event)
    
    def get_system_status(self) -> Dict[str, float]:
        """Mock system status retrieval."""
        return self.system_status.copy()
    
    def simulate_detection_sequence(self, duration: float = 30.0, 
                                   detection_rate: float = 0.1):
        """Simulate a sequence of detection events."""
        import time
        import random
        
        start_time = time.time()
        current_time = 0.0
        
        while current_time < duration:
            if random.random() < detection_rate:
                detection = {
                    "timestamp": current_time,
                    "confidence": random.uniform(0.6, 0.95),
                    "class_label": random.choice([
                        "pedestrian", "cyclist", "vehicle"
                    ]),
                    "bounding_box": {
                        "x": random.randint(50, 300),
                        "y": random.randint(50, 200), 
                        "width": random.randint(40, 100),
                        "height": random.randint(80, 150)
                    }
                }
                self.send_detection_event(detection)
            
            time.sleep(0.1)  # 10 FPS simulation
            current_time += 0.1

class MockFileStorageService:
    """Mock file storage service for testing."""
    
    def __init__(self):
        self.stored_files = {}
        self.upload_errors = {}
    
    def save_file(self, file_data, filename: str, directory: str = "uploads") -> str:
        """Mock file saving."""
        if filename in self.upload_errors:
            raise Exception(self.upload_errors[filename])
        
        file_path = f"/{directory}/{filename}"
        self.stored_files[file_path] = {
            "size": len(file_data) if hasattr(file_data, '__len__') else 1024,
            "content_type": "video/mp4",
            "uploaded_at": "2024-01-15T10:00:00Z"
        }
        return file_path
    
    def delete_file(self, file_path: str) -> bool:
        """Mock file deletion."""
        if file_path in self.stored_files:
            del self.stored_files[file_path]
            return True
        return False
    
    def file_exists(self, file_path: str) -> bool:
        """Mock file existence check."""
        return file_path in self.stored_files
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Mock file info retrieval."""
        return self.stored_files.get(file_path)
    
    def simulate_upload_error(self, filename: str, error_message: str):
        """Simulate upload error for testing."""
        self.upload_errors[filename] = error_message

# Pytest fixtures for mock services
@pytest.fixture
def mock_ground_truth_service():
    """Mock ground truth service fixture."""
    return MockGroundTruthService()

@pytest.fixture
def mock_raspberry_pi_service():
    """Mock Raspberry Pi service fixture."""
    return MockRaspberryPiService()

@pytest.fixture
def mock_file_storage_service():
    """Mock file storage service fixture."""
    return MockFileStorageService()
```

## Test Execution Strategies

### Parallel Test Execution

```python
# pytest.ini configuration for parallel execution

[tool:pytest]
addopts = 
    --strict-markers
    --strict-config
    --verbose
    --tb=short
    --cov=src
    --cov-report=html:tests/reports/coverage
    --cov-report=term-missing
    --cov-fail-under=80
    --junitxml=tests/reports/junit.xml
    --html=tests/reports/report.html
    --self-contained-html
    --maxfail=5
    --disable-warnings
    -n auto  # Parallel execution with auto worker count

markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (database, services)
    e2e: End-to-end tests (slow, full workflow)
    performance: Performance and load tests
    slow: Slow running tests (skipped in quick runs)
    hardware: Hardware dependent tests
    websocket: WebSocket related tests
    database: Database dependent tests
    model: AI model related tests
    smoke: Smoke tests for basic functionality

# Test selection based on markers
# pytest -m "unit and not slow"           # Fast unit tests only
# pytest -m "integration or e2e"          # Integration and E2E tests
# pytest -m "not hardware"                # Skip hardware tests
# pytest -m "smoke"                       # Smoke tests only
```

### Test Environment Management

```python
# tests/utils/environment.py

import os
import pytest
from enum import Enum
from typing import Dict, Any

class TestEnvironment(Enum):
    UNIT = "unit"
    INTEGRATION = "integration" 
    E2E = "e2e"
    PERFORMANCE = "performance"

class EnvironmentManager:
    """Manage different test environments and configurations."""
    
    def __init__(self):
        self.current_env = self._detect_environment()
        self.config = self._load_config()
    
    def _detect_environment(self) -> TestEnvironment:
        """Detect current test environment from environment variables."""
        env_name = os.getenv("TEST_ENV", "unit").lower()
        try:
            return TestEnvironment(env_name)
        except ValueError:
            return TestEnvironment.UNIT
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration based on test environment."""
        base_config = {
            "database_url": "sqlite:///:memory:",
            "redis_url": "redis://localhost:6379/15",
            "file_storage_path": "/tmp/test_uploads",
            "jwt_secret": "test_secret_key",
            "api_base_url": "http://testserver"
        }
        
        env_configs = {
            TestEnvironment.UNIT: {
                "use_real_services": False,
                "create_test_files": False,
                "cleanup_after_test": True
            },
            TestEnvironment.INTEGRATION: {
                "database_url": "postgresql://test:test@localhost:5432/test_db",
                "use_real_services": True,
                "create_test_files": True,
                "cleanup_after_test": True
            },
            TestEnvironment.E2E: {
                "database_url": "postgresql://test:test@localhost:5432/e2e_db",
                "api_base_url": "http://localhost:8000",
                "browser_headless": True,
                "use_real_services": True,
                "create_test_files": True,
                "cleanup_after_test": False  # Keep for debugging
            },
            TestEnvironment.PERFORMANCE: {
                "database_url": "postgresql://test:test@localhost:5432/perf_db",
                "use_real_services": True,
                "generate_large_datasets": True,
                "performance_thresholds": {
                    "api_response_time": 0.2,  # 200ms
                    "video_processing_time": 60,  # 60s per minute of video
                    "concurrent_users": 100
                }
            }
        }
        
        config = base_config.copy()
        config.update(env_configs.get(self.current_env, {}))
        
        # Override with environment variables
        for key in config:
            env_key = f"TEST_{key.upper()}"
            if env_key in os.environ:
                config[key] = os.environ[env_key]
        
        return config
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def is_environment(self, env: TestEnvironment) -> bool:
        """Check if current environment matches."""
        return self.current_env == env
    
    def setup_test_data(self):
        """Setup test data based on environment."""
        if self.get_config("create_test_files", False):
            self._create_test_files()
        
        if self.get_config("generate_large_datasets", False):
            self._generate_performance_datasets()
    
    def _create_test_files(self):
        """Create test video and image files."""
        import cv2
        import numpy as np
        from pathlib import Path
        
        test_files_dir = Path(self.get_config("file_storage_path"))
        test_files_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test video
        video_path = test_files_dir / "test_video.mp4"
        if not video_path.exists():
            self._create_test_video(video_path)
        
        # Create test images
        for i in range(5):
            image_path = test_files_dir / f"test_image_{i}.jpg"
            if not image_path.exists():
                self._create_test_image(image_path)
    
    def _create_test_video(self, output_path, duration=30, fps=30):
        """Create synthetic test video."""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        height, width = 480, 640
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        
        total_frames = duration * fps
        for frame_idx in range(total_frames):
            # Create frame with moving objects
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Moving pedestrian simulation
            x = int((frame_idx / total_frames) * (width - 50))
            cv2.rectangle(frame, (x, 200), (x + 30, 300), (0, 255, 0), -1)
            
            # Static vehicle simulation
            cv2.rectangle(frame, (400, 350), (550, 450), (255, 0, 0), -1)
            
            out.write(frame)
        
        out.release()
    
    def _create_test_image(self, output_path):
        """Create synthetic test image."""
        height, width = 480, 640
        image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        
        # Add some recognizable objects
        cv2.rectangle(image, (100, 100), (150, 200), (0, 255, 0), -1)  # Person
        cv2.rectangle(image, (300, 250), (450, 350), (255, 0, 0), -1)  # Vehicle
        
        cv2.imwrite(str(output_path), image)
    
    def _generate_performance_datasets(self):
        """Generate large datasets for performance testing."""
        # This would generate large amounts of test data
        # for performance and load testing scenarios
        pass

# Global environment manager
env_manager = EnvironmentManager()

@pytest.fixture(scope="session")
def test_environment():
    """Test environment fixture."""
    env_manager.setup_test_data()
    return env_manager
```

## Continuous Integration Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml

name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  PYTHON_VERSION: "3.11"
  NODE_VERSION: "18"
  POSTGRES_VERSION: "14"

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Cache Python dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=src --cov-report=xml
        env:
          TEST_ENV: unit
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ -v
        env:
          TEST_ENV: integration
          DATABASE_URL: postgresql://test:test@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/1
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

  frontend-tests:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Run unit tests
        run: |
          cd frontend
          npm test -- --coverage --watchAll=false
      
      - name: Run build test
        run: |
          cd frontend
          npm run build
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          directory: ./frontend/coverage

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: e2e_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          cd frontend && npm ci
      
      - name: Build frontend
        run: |
          cd frontend
          npm run build
      
      - name: Start services
        run: |
          # Start backend in background
          uvicorn main:app --host 0.0.0.0 --port 8000 &
          # Start frontend in background
          cd frontend && npx serve -s build -l 3000 &
          # Wait for services to be ready
          sleep 10
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/e2e_db
      
      - name: Install Playwright
        run: |
          pip install playwright
          playwright install chromium
      
      - name: Run E2E tests
        run: |
          pytest tests/e2e/ -v --html=tests/reports/e2e-report.html
        env:
          TEST_ENV: e2e
          API_BASE_URL: http://localhost:8000
          FRONTEND_URL: http://localhost:3000
      
      - name: Upload E2E test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: e2e-test-results
          path: tests/reports/

  performance-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install locust
      
      - name: Run performance tests
        run: |
          pytest tests/performance/ -v --html=tests/reports/performance-report.html
        env:
          TEST_ENV: performance
      
      - name: Upload performance results
        uses: actions/upload-artifact@v3
        with:
          name: performance-test-results
          path: tests/reports/

  security-scan:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Run security scan
        uses: securecodewarrior/github-action-add-sarif@v1
        with:
          sarif-file: security-scan-results.sarif
      
      - name: Run dependency scan
        run: |
          pip install safety
          safety check --json --output safety-report.json
      
      - name: Upload security results
        uses: actions/upload-artifact@v3
        with:
          name: security-scan-results
          path: |
            security-scan-results.sarif
            safety-report.json
```

## Test Reporting and Analytics

### Allure Test Reporting

```python
# tests/utils/allure_helpers.py

import allure
from allure_commons.types import AttachmentType
import json
import traceback
from typing import Any, Dict

class AllureReporter:
    """Enhanced Allure reporting utilities."""
    
    @staticmethod
    def attach_json_data(data: Dict[str, Any], name: str = "Test Data"):
        """Attach JSON data to test report."""
        allure.attach(
            json.dumps(data, indent=2, default=str),
            name=name,
            attachment_type=AttachmentType.JSON
        )
    
    @staticmethod
    def attach_api_request(method: str, url: str, headers: Dict = None, 
                          body: Any = None):
        """Attach API request details."""
        request_data = {
            "method": method,
            "url": url,
            "headers": headers or {},
            "body": body
        }
        AllureReporter.attach_json_data(request_data, "API Request")
    
    @staticmethod
    def attach_api_response(status_code: int, headers: Dict = None, 
                           body: Any = None):
        """Attach API response details."""
        response_data = {
            "status_code": status_code,
            "headers": headers or {},
            "body": body
        }
        AllureReporter.attach_json_data(response_data, "API Response")
    
    @staticmethod
    def attach_database_query(query: str, parameters: Dict = None):
        """Attach database query details."""
        query_data = {
            "query": query,
            "parameters": parameters or {}
        }
        AllureReporter.attach_json_data(query_data, "Database Query")
    
    @staticmethod  
    def attach_error_details(exception: Exception):
        """Attach error details and traceback."""
        error_data = {
            "exception_type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc()
        }
        AllureReporter.attach_json_data(error_data, "Error Details")
    
    @staticmethod
    def step(title: str):
        """Create an Allure step context manager."""
        return allure.step(title)

# Pytest plugin for automatic Allure enhancements
class AllurePytestPlugin:
    """Pytest plugin for enhanced Allure reporting."""
    
    def pytest_runtest_call(self, item):
        """Add test metadata to Allure report."""
        # Add test markers as labels
        for marker in item.iter_markers():
            allure.dynamic.label("marker", marker.name)
        
        # Add test file path
        allure.dynamic.label("test_file", str(item.fspath.basename))
        
        # Add test function name
        allure.dynamic.label("test_function", item.name)
    
    def pytest_runtest_makereport(self, item, call):
        """Attach additional information on test failure."""
        if call.when == "call" and call.excinfo is not None:
            AllureReporter.attach_error_details(call.excinfo.value)
```

This comprehensive test automation framework provides a solid foundation for ensuring the quality and reliability of the AI Model Validation Platform through systematic, scalable, and maintainable testing practices.