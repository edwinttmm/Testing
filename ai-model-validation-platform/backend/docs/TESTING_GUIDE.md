# Testing Guide - AI Model Validation Platform

## Overview

This document describes the comprehensive test suite for the AI Model Validation Platform backend, covering all critical fixes and functionality.

## Table of Contents

1. [Test Structure](#test-structure)
2. [Running Tests](#running-tests)
3. [Test Categories](#test-categories)
4. [Coverage Requirements](#coverage-requirements)
5. [CI/CD Integration](#cicd-integration)
6. [Writing Tests](#writing-tests)
7. [Performance Benchmarks](#performance-benchmarks)

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                      # Shared fixtures and configuration
├── unit/                            # Unit tests
│   ├── test_timing_quality_schema.py
│   └── test_security_validation.py
├── integration/                     # Integration tests
│   └── test_all_fixes_integration.py
├── performance/                     # Load and performance tests
│   └── test_load_performance.py
├── security/                        # Security tests
│   └── test_security_fixes.py
└── regression/                      # Regression tests
    └── test_no_regressions.py
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r tests/requirements-test.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Performance tests
pytest tests/performance/ -v

# Security tests
pytest tests/security/ -v

# Regression tests
pytest tests/regression/ -v
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html --cov-report=term-missing
```

View HTML coverage report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run Specific Tests

```bash
# Run a specific test file
pytest tests/unit/test_timing_quality_schema.py -v

# Run a specific test class
pytest tests/unit/test_timing_quality_schema.py::TestTimingQualitySchema -v

# Run a specific test function
pytest tests/unit/test_timing_quality_schema.py::TestTimingQualitySchema::test_timing_degraded_field -v

# Run tests matching a pattern
pytest -k "timing" -v
```

### Run Tests in Parallel

```bash
pytest -n auto  # Uses all available CPU cores
pytest -n 4     # Uses 4 workers
```

## Test Categories

### 1. Unit Tests

**Purpose**: Test individual components in isolation

**Location**: `tests/unit/`

**Coverage**:
- Database schema changes (timing quality fields)
- Security validation functions
- Input sanitization
- UUID validation

**Run**:
```bash
pytest tests/unit/ -v
```

### 2. Integration Tests

**Purpose**: Test multiple components working together

**Location**: `tests/integration/`

**Coverage**:
- Complete session lifecycle with all fixes
- MVCC retry logic
- Session verification
- Quality filtering across tables

**Run**:
```bash
pytest tests/integration/ -v
```

### 3. Performance Tests

**Purpose**: Verify performance optimizations and prevent degradation

**Location**: `tests/performance/`

**Coverage**:
- Concurrent session creation (25+ sessions)
- Connection pool efficiency
- Query performance
- Memory usage under load

**Benchmarks**:
- Concurrent sessions: < 3x baseline degradation
- Detection throughput: > 20 events/sec
- Query time: < 0.5s for complex filtered queries

**Run**:
```bash
pytest tests/performance/ -v
```

### 4. Security Tests

**Purpose**: Verify security fixes and prevent vulnerabilities

**Location**: `tests/security/`

**Coverage**:
- SQL injection prevention
- XSS prevention
- Input validation
- Authentication/authorization
- Rate limiting
- Data leakage prevention

**Run**:
```bash
pytest tests/security/ -v
```

### 5. Regression Tests

**Purpose**: Ensure fixes don't break existing functionality

**Location**: `tests/regression/`

**Coverage**:
- Basic CRUD operations
- API endpoints
- Database relationships
- Ground truth matching
- Backwards compatibility

**Run**:
```bash
pytest tests/regression/ -v
```

## Coverage Requirements

### Minimum Coverage Targets

| Metric     | Target | Current |
|------------|--------|---------|
| Statements | 80%    | TBD     |
| Branches   | 75%    | TBD     |
| Functions  | 80%    | TBD     |
| Lines      | 80%    | TBD     |

### Critical Modules (90%+ coverage required)

- `models.py` - Database models
- `utils/validation.py` - Security validation
- `api/sessions.py` - Session management
- `database.py` - Database configuration

### Generate Coverage Report

```bash
pytest --cov=. --cov-report=term-missing --cov-report=html
```

### Coverage Badge

Update badge in README:
```bash
coverage-badge -o coverage.svg
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_validation_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r tests/requirements-test.txt

    - name: Run tests
      env:
        TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_validation_db
      run: |
        pytest --cov=. --cov-report=xml --cov-report=term

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

Install:
```bash
pre-commit install
```

## Writing Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Test Structure

```python
import pytest
from models import TestSession

class TestSessionCreation:
    """Test session creation functionality"""

    def test_valid_session_creation(self, db_session, sample_project_id):
        """Test that valid session is created successfully"""
        # Arrange
        session = TestSession(
            id=str(uuid.uuid4()),
            project_id=sample_project_id
        )

        # Act
        db_session.add(session)
        db_session.commit()

        # Assert
        assert session.id is not None
        assert session.project_id == sample_project_id

    def test_invalid_session_raises_error(self, db_session):
        """Test that invalid session raises ValidationError"""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError):
            session = TestSession(
                id="invalid-uuid",
                project_id=None
            )
```

### Using Fixtures

```python
@pytest.fixture
def sample_session(db_session, sample_project_id):
    """Create a sample session for testing"""
    session = TestSession(
        id=str(uuid.uuid4()),
        project_id=sample_project_id
    )
    db_session.add(session)
    db_session.commit()
    return session

def test_with_fixture(sample_session):
    """Test using the sample_session fixture"""
    assert sample_session.id is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("voltage,expected", [
    (4.0, True),
    (4.5, True),
    (5.0, True),
    (3.5, False),
])
def test_voltage_validation(voltage, expected):
    """Test voltage validation with multiple values"""
    result = validate_voltage(voltage)
    assert result == expected
```

## Performance Benchmarks

### Baseline Metrics

| Operation                  | Baseline | Current | Target       |
|----------------------------|----------|---------|--------------|
| Single session creation    | 0.1s     | TBD     | < 0.3s       |
| 25 concurrent sessions     | 0.7s     | TBD     | < 2.1s (3x)  |
| Detection event creation   | 0.05s    | TBD     | < 0.15s      |
| Complex filtered query     | 0.2s     | TBD     | < 0.5s       |
| 100 detections throughput  | 5s       | TBD     | < 5s         |

### Running Performance Tests

```bash
# Run all performance tests
pytest tests/performance/ -v

# Run with detailed output
pytest tests/performance/ -v -s

# Run specific performance test
pytest tests/performance/test_load_performance.py::TestConcurrentPerformance::test_concurrent_session_creation_no_degradation -v
```

### Performance Test Output Example

```
✅ Concurrent session creation performance:
   Total time: 1.85s
   Average: 0.074s (target: <0.300s)
   Min: 0.062s, Max: 0.128s
   Performance ratio: 0.7x baseline
```

## Manual Testing

### Database Setup

```bash
# Create test database
createdb test_validation_db

# Run migrations
alembic upgrade head

# Seed test data
python scripts/seed_test_data.py
```

### Manual Test Cases

1. **Session Creation Flow**
   - Create project
   - Start test session
   - Capture detections
   - Verify timing quality flags

2. **Concurrent Load Test**
   - Start 25 sessions simultaneously
   - Monitor timing degradation
   - Verify all sessions complete

3. **Security Validation**
   - Try SQL injection payloads
   - Verify 400 error responses
   - Check logs for blocked attempts

4. **Quality Filtering**
   - Create mixed quality sessions
   - Query for high-quality data only
   - Verify filtering works correctly

## Troubleshooting

### Common Issues

**Issue**: Tests fail with database connection error

**Solution**:
```bash
# Check database is running
pg_isready

# Verify connection string
echo $TEST_DATABASE_URL

# Reset test database
dropdb test_validation_db
createdb test_validation_db
```

**Issue**: Tests are slow

**Solution**:
```bash
# Run tests in parallel
pytest -n auto

# Skip slow tests
pytest -m "not slow"

# Use faster database (in-memory SQLite for unit tests)
# Update conftest.py to use SQLite for unit tests
```

**Issue**: Coverage report incomplete

**Solution**:
```bash
# Clear coverage data
coverage erase

# Run tests with coverage
pytest --cov=. --cov-report=html

# Check .coveragerc configuration
cat .coveragerc
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Fast Tests**: Unit tests should run in < 100ms
3. **Clear Names**: Test names should describe what they test
4. **Arrange-Act-Assert**: Structure tests clearly
5. **Mock External Services**: Keep tests isolated
6. **Test Edge Cases**: Include boundary conditions
7. **Security First**: Test all validation rules
8. **Performance Baselines**: Track performance over time

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/14/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Coverage.py](https://coverage.readthedocs.io/)

## Support

For test-related issues:
1. Check this documentation
2. Review test output and logs
3. Create issue with test failure details
4. Include coverage report if relevant
