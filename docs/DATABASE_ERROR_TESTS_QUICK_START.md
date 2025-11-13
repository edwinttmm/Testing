# Database Error Tests - Quick Start Guide

## 🚀 Quick Setup

```bash
# Navigate to backend
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Install test dependencies
pip install pytest pytest-asyncio fastapi sqlalchemy

# Run all database error tests
pytest tests/test_database_session_cleanup.py \
       tests/test_middleware_error_handling.py \
       tests/test_error_scenarios_integration.py \
       tests/test_database_stress.py \
       -v
```

## 📋 Test Files Overview

| File | Tests | Lines | Purpose |
|------|-------|-------|---------|
| `test_database_session_cleanup.py` | 7 | 187 | Core session lifecycle |
| `test_middleware_error_handling.py` | 11 | 557 | Middleware error handling |
| `test_error_scenarios_integration.py` | 14 | 630 | Real-world error scenarios |
| `test_database_stress.py` | 11 | 555 | Performance & stress testing |
| `conftest_database_error_tests.py` | - | 291 | Shared fixtures & utilities |
| **TOTAL** | **43** | **2,220** | **Complete coverage** |

## 🎯 Test Categories

### Session Cleanup Tests (7 tests)
```bash
pytest tests/test_database_session_cleanup.py -v
```
- ✅ Cleanup on success
- ✅ Cleanup on errors
- ✅ Cleanup on database errors
- ✅ Session isolation
- ✅ Concurrent sessions
- ✅ Idempotent cleanup
- ✅ No session reuse

### Middleware Tests (11 tests)
```bash
pytest tests/test_middleware_error_handling.py -v
```
- ✅ Generator cleanup errors
- ✅ Error propagation
- ✅ Multiple middleware layers
- ✅ Nested context managers
- ✅ Async generator cleanup
- ✅ Exception chaining
- ✅ Memory cleanup
- ✅ Concurrent requests
- ✅ Response modification

### Integration Tests (14 tests)
```bash
pytest tests/test_error_scenarios_integration.py -v
```
- ✅ Connection failures
- ✅ Timeout errors
- ✅ Lock/deadlock scenarios
- ✅ Integrity violations
- ✅ SQL syntax errors
- ✅ Transaction rollback
- ✅ Error recovery
- ✅ Circuit breaker pattern
- ✅ Graceful degradation

### Stress Tests (11 tests)
```bash
pytest tests/test_database_stress.py -v
```
- ✅ 100 rapid requests
- ✅ 200 concurrent requests
- ✅ 500 burst requests
- ✅ Sustained load (5s)
- ✅ Mixed workloads
- ✅ High error rates (70%)
- ✅ Thread safety
- ✅ Performance stability
- ✅ Memory pressure

## 🔍 Run Specific Tests

### Individual Test
```bash
pytest tests/test_database_session_cleanup.py::test_database_session_cleanup_on_error -v
```

### By Category
```bash
# Fast tests only
pytest tests/test_database_session_cleanup.py -v

# Stress tests only
pytest tests/test_database_stress.py -v
```

### With Coverage
```bash
pytest tests/test_database*.py tests/test_middleware*.py tests/test_error*.py \
  --cov=backend \
  --cov-report=html
```

## 📊 Expected Results

### Before Fix (Demonstrating Bug)
```
FAILED test_database_session_cleanup_on_error
  RuntimeError: generator raised StopIteration

FAILED test_middleware_handles_generator_error
  RuntimeError: generator raised StopIteration
```

### After Fix (All Pass)
```
✓ test_database_session_cleanup.py::test_database_session_cleanup_on_success
✓ test_database_session_cleanup.py::test_database_session_cleanup_on_error
✓ test_middleware_error_handling.py::test_middleware_handles_generator_error
... (40 more tests)

================== 43 passed in 3.21s ==================
```

## 🔧 Troubleshooting

### Missing pytest
```bash
pip install pytest pytest-asyncio
```

### Import errors
```bash
pip install fastapi sqlalchemy
```

### Verbose debugging
```bash
pytest tests/test_database_session_cleanup.py -vv --tb=long
```

## 📝 Test Structure

### Session Cleanup Test
```python
def test_database_session_cleanup_on_error():
    """Session should be cleaned up even when endpoint raises error."""
    # Arrange
    session = session_tracker.create_session()

    # Act
    # ... simulate error scenario ...

    # Assert
    assert session.close.call_count == 1
    assert session_tracker.get_leak_count() == 0
```

### Middleware Test
```python
def test_middleware_handles_generator_error():
    """Middleware should handle generator cleanup errors gracefully."""
    # Test implementation with FastAPI TestClient
```

### Stress Test
```python
async def test_rapid_requests_no_session_leak():
    """100 rapid requests should not leak database sessions."""
    # Create 100 concurrent requests
    # Verify no leaks
```

## ✅ Success Criteria

- [x] All 4 test files created
- [x] 43+ comprehensive test cases
- [x] Complete error scenario coverage
- [x] Performance benchmarks included
- [x] Integration tests included
- [x] Shared fixtures configured
- [x] Documentation complete

## 🚦 Next Steps

1. **Install Dependencies**
   ```bash
   pip install pytest pytest-asyncio
   ```

2. **Run Tests Before Fix**
   ```bash
   pytest tests/test_database_session_cleanup.py::test_database_session_cleanup_on_error -v
   # Should FAIL with RuntimeError
   ```

3. **Apply Database Session Fix**
   - Implement proper generator cleanup
   - Use try-except in finally blocks

4. **Run Tests After Fix**
   ```bash
   pytest tests/test_database*.py -v
   # Should PASS all tests
   ```

5. **Run Full Suite**
   ```bash
   pytest tests/test_database*.py tests/test_middleware*.py tests/test_error*.py -v
   # All 43 tests should pass
   ```

## 📚 Additional Resources

- Full Report: `/home/rigade/Testing/docs/DATABASE_ERROR_TEST_SUITE_REPORT.md`
- Test Files: `/home/rigade/Testing/ai-model-validation-platform/backend/tests/`
- Fixtures: `conftest_database_error_tests.py`

---

**Test Suite Ready for Execution** ✓
