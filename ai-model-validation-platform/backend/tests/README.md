# Ground Truth Fixes Test Suite

Production-grade tests for all 6 critical ground truth matching fixes.

## Test Coverage

### Unit Tests (`test_ground_truth_fixes.py`)
- **Issue #6**: Soft delete behavior and active session protection
- **Issue #5**: N+1 query elimination with batch loading  
- **Issue #2**: Batch limit validation for 25k+ GT objects
- **Issue #1**: Orchestrator sync on video end
- **Issue #4**: Detection count accuracy
- **Issue #3**: Validation endpoint responses

### Integration Tests (`test_integration_ground_truth.py`)
- End-to-end multi-video sequences
- Issue #1 + #4 interaction (orchestrator + counts)
- Issue #2 + #5 performance (batch + N+1)
- Issue #6 protection during active sessions

### Frontend Tests (`frontend/src/__tests__/GTValidation.test.tsx`)
- Validation modal rendering
- "Start Anyway" user flow
- API error handling
- Accessibility compliance

## Running Tests

### Run all tests
```bash
cd backend/tests
pytest -v
```

### Run specific test file
```bash
pytest test_ground_truth_fixes.py -v
```

### Run with coverage
```bash
pytest --cov=services --cov=crud --cov-report=html
```

### Run performance benchmarks
```bash
pytest -m performance -v
```

### Run integration tests only
```bash
pytest -m integration -v
```

## Test Requirements

- Python 3.9+
- PostgreSQL or SQLite (in-memory for tests)
- All dependencies in `requirements.txt`

## Coverage Goals

- **Target**: >90% code coverage for new code
- **Critical paths**: 100% coverage
- **Performance tests**: Thresholds must pass

## Performance Thresholds

| Test | Threshold |
|------|-----------|
| 100-video sequence | <5 seconds |
| 25k GT query | <1 second |
| N+1 elimination | O(1) queries |
| Batch operations | <50 queries |

## Test Data

Tests use factories and fixtures to generate:
- Multi-video sequences (10-100 videos)
- Large GT datasets (25k+ objects)
- Active/completed test sessions
- Detection events with timing data

## Continuous Integration

Tests run automatically on:
- Pull requests to main branch
- Commits to release branches
- Nightly performance regression checks

## Troubleshooting

### Tests fail with database errors
- Check database connection in `conftest.py`
- Ensure migrations are up to date
- Clear test database: `pytest --create-db`

### Performance tests timeout
- Increase timeout: `pytest --timeout=300`
- Check system resources
- Run with profiling: `pytest --profile`

### Coverage below threshold
- Run: `pytest --cov-report=term-missing`
- Identify uncovered lines
- Add targeted tests

## Contributing

When adding new ground truth features:
1. Write tests first (TDD)
2. Ensure >90% coverage
3. Add performance benchmarks
4. Update this README
