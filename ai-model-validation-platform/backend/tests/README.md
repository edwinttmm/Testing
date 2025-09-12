# Video Validation Test Suite

Comprehensive test suite for video validation status fixes and HIL test execution functionality.

## Overview

This test suite covers the complete video lifecycle from upload to HIL testing, ensuring proper status transitions, validation logic, and error handling.

## Test Structure

```
tests/
├── unit/                           # Unit tests
│   └── test_video_status_transitions.py
├── integration/                    # API integration tests  
│   └── test_video_validation_api.py
├── e2e/                           # End-to-end workflow tests
│   └── test_video_validation_workflow.py
├── frontend/                      # Frontend API tests
│   └── test_video_filtering_frontend.py
├── migration/                     # Data migration tests
│   └── test_video_status_migration.py
├── performance/                   # Performance & error tests
│   ├── test_video_validation_performance.py
│   └── test_video_status_error_handling.py
└── test_video_validation_suite.py # Test runner
```

## Test Categories

### 1. Unit Tests (`unit/`)
- **VideoStatus enum validation**
- **Status transition logic** 
- **Business rule validation**
- **Video filtering logic**
- **Ground truth integration**

**Key Test Cases:**
- Valid/invalid status transitions
- Video ready for HIL testing logic
- Batch status update operations
- Status filtering and counting

### 2. Integration Tests (`integration/`)
- **Video validation API endpoints**
- **Status update endpoints**
- **HIL test session creation**
- **Video listing with filters**
- **Batch operations**

**Key Test Cases:**
- GET /api/videos with status filtering
- PATCH /api/videos/{id}/status
- GET /api/videos/hil-ready
- POST /api/enhanced-test/sessions
- Workflow integration testing

### 3. End-to-End Tests (`e2e/`)
- **Complete video validation workflow**
- **Upload → Processing → Validation → HIL Testing**
- **Multiple video scenarios**
- **Error recovery workflows**

**Key Test Cases:**
- Full video upload to HIL testing workflow
- Multi-video state management
- Error state recovery
- HIL page video loading

### 4. Frontend Tests (`frontend/`)
- **Frontend API consumption**
- **Video filtering UI support**
- **HIL Test Execution page APIs**
- **Real-time status updates**

**Key Test Cases:**
- Video status display mapping
- Filter options and pagination
- HIL eligible video loading
- Status change notifications

### 5. Migration Tests (`migration/`)
- **Legacy data migration**
- **Status mapping validation**
- **Batch migration performance**
- **Data integrity validation**

**Key Test Cases:**
- Old status → New status mapping
- Consistency validation post-migration
- Rollback capability
- Performance with large datasets

### 6. Performance & Error Tests (`performance/`)
- **Large dataset performance**
- **Concurrent operations**
- **Memory usage optimization**
- **Error handling and recovery**

**Key Test Cases:**
- 1000+ video query performance
- Concurrent status updates
- Memory usage under load
- Invalid state transition handling

## Running Tests

### Run All Tests
```bash
# Run comprehensive test suite
python tests/test_video_validation_suite.py

# Run with pytest directly
pytest tests/ -v --cov=. --cov-report=html
```

### Run Specific Categories
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only  
pytest tests/integration/ -v

# Performance tests (may take longer)
pytest tests/performance/ -v --timeout=300
```

### Run Individual Test Files
```bash
# Test video status transitions
pytest tests/unit/test_video_status_transitions.py -v

# Test API endpoints
pytest tests/integration/test_video_validation_api.py -v

# Test complete workflows
pytest tests/e2e/test_video_validation_workflow.py -v
```

## Test Data Management

### Test Databases
Each test category uses isolated SQLite databases:
- `test_video_validation.db` - Integration tests
- `test_e2e_video_validation.db` - E2E tests
- `test_frontend_video_filtering.db` - Frontend tests
- `test_migration_*.db` - Migration tests
- `test_performance_video_validation.db` - Performance tests

### Fixtures and Setup
- **Projects**: Test projects with different configurations
- **Videos**: Videos in various status states for comprehensive testing
- **Ground Truth**: Mock ground truth data for validation testing
- **Test Files**: Temporary video files for upload testing

## Coverage Goals

- **Overall Coverage**: ≥80%
- **Critical Paths**: ≥90% (status transitions, validation logic)
- **Error Handling**: ≥75%
- **API Endpoints**: ≥85%

## Key Test Scenarios

### 1. Video Status Lifecycle
```
uploaded → processing → pending_validation → validated
    ↓           ↓              ↓              ↓
  error ←――――――――――――――――――――――――――――――――――――――→ (recovery)
```

### 2. HIL Test Execution Requirements
- Video must be `validated`
- Must have `ground_truth_generated = True`
- Must have `processing_status = "completed"`
- Must have validated ground truth objects

### 3. Error Recovery Scenarios
- Database connection failures
- Concurrent update conflicts
- Processing timeouts
- File access errors
- Data consistency issues

## Configuration

### pytest.ini
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --cov=.
    --cov-report=html
    --cov-report=term-missing
    --durations=10
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    performance: Performance tests
    slow: Tests that take longer to run
```

### Environment Variables
```bash
# Test environment settings
export TESTING=true
export DATABASE_URL=sqlite:///./test.db
export LOG_LEVEL=WARNING
```

## Performance Benchmarks
- **Video listing**: <1s for 1000 videos
- **Status updates**: <0.1s per video
- **Batch operations**: <5s for 250 updates
- **Memory usage**: <50MB increase for batch operations

## Contributing

When adding new video validation tests:

1. **Follow the existing structure** - Place tests in appropriate categories
2. **Use descriptive test names** - Clearly indicate what is being tested
3. **Include both positive and negative cases** - Test success and failure scenarios
4. **Mock external dependencies** - Keep tests isolated and fast
5. **Add proper cleanup** - Ensure test databases are cleaned up
6. **Update this README** - Document new test scenarios