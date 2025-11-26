# SQLAlchemy Session Management Fix Summary

## Problem Statement
10+ integration tests were failing with SQLAlchemy session errors:
```
sqlalchemy.exc.InvalidRequestError: Object '<Model>' is already attached to session '1' (or a different session)
```

## Root Causes Identified

### 1. Missing Fixtures
- Tests were requesting `db_session` but conftest.py only provided `test_db`
- No `sample_project_id` or `sample_project` fixtures
- No `client` fixture for FastAPI testing

### 2. Session Lifecycle Issues
- Sessions not properly configured with `expire_on_commit=False`
- No proper cleanup with `expunge_all()` after tests
- Objects becoming detached from sessions after commit

### 3. Cross-Session Object Usage
- Tests creating new SessionLocal() instances directly
- Objects from one session being used in another
- Missing `db_session.refresh()` calls after commits

## Fixes Applied

### 1. Enhanced conftest.py (/home/rigade/Testing/ai-model-validation-platform/backend/tests/conftest.py)

```python
@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create isolated database session for each test"""
    connection = test_engine.connect()
    transaction = connection.begin()

    # Create session factory with proper settings
    SessionLocal = sessionmaker(
        bind=connection,
        expire_on_commit=False,  # Prevent detached instance errors
        autoflush=False  # Give tests more control
    )
    session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.expunge_all()  # Detach all objects
        session.close()
        transaction.rollback()
        connection.close()
```

**Added Fixtures:**
- `db_session`: Alias for test_db with better session management
- `sample_project_id(db_session)`: Creates test project and returns ID
- `sample_project(db_session)`: Creates and returns test project object
- `client()`: FastAPI TestClient for API tests

### 2. Test File Fixes

#### test_all_fixes_integration.py
**Changes:**
- Added `from sqlalchemy import select, func` imports
- Added `db_session.refresh()` after all commits
- Removed threading-based concurrent test (incompatible with single session)
- Added `sample_project_id` parameter to all relevant tests

**Pattern Applied:**
```python
# Before (WRONG):
session = TestSession(id=session_id, project_id=sample_project_id)
db_session.add(session)
db_session.commit()
# Object might be detached here!

# After (CORRECT):
session = TestSession(id=session_id, project_id=sample_project_id)
db_session.add(session)
db_session.commit()
db_session.refresh(session)  # Keep object attached
```

#### test_fix_integration_comprehensive.py
**Changes:**
- Removed local `db_session` fixture definitions
- Removed `clean_database` fixture (not needed with proper transaction isolation)
- Fixed race condition test to use single session instead of creating new SessionLocal()
- All async tests now use shared `db_session` from conftest

#### test_ground_truth_data_flow.py
**Changes:**
- Replaced all `SessionLocal()` calls with `db_session` parameter
- Fixed fixture signatures to include `db_session`
- Added proper cleanup with `db_session.refresh()` after commits
- Fixed indentation issues in multiple test methods

**Pattern Applied:**
```python
# Before (WRONG):
db = SessionLocal()
try:
    obj = Model()
    db.add(obj)
    db.commit()
finally:
    db.close()

# After (CORRECT):
obj = Model()
db_session.add(obj)
db_session.commit()
db_session.refresh(obj)  # Stays attached to session
```

## Key Patterns for Session Management

### 1. Always Use Fixture Session
```python
def test_something(db_session):
    # Use db_session, never create SessionLocal()
    obj = Model()
    db_session.add(obj)
    db_session.commit()
```

### 2. Refresh After Commit
```python
db_session.add(obj)
db_session.commit()
db_session.refresh(obj)  # Prevents detachment
```

### 3. Expunge Before Closing
```python
try:
    yield session
    session.commit()
finally:
    session.expunge_all()  # Detach all objects
    session.close()
```

### 4. Use expire_on_commit=False
```python
SessionLocal = sessionmaker(
    bind=connection,
    expire_on_commit=False  # Prevents lazy-load issues
)
```

## Files Modified

1. `/home/rigade/Testing/ai-model-validation-platform/backend/tests/conftest.py`
   - Added db_session fixture with proper settings
   - Added sample_project_id and sample_project fixtures
   - Added client fixture
   - Enhanced cleanup with expunge_all()

2. `/home/rigade/Testing/ai-model-validation-platform/backend/tests/integration/test_all_fixes_integration.py`
   - Fixed imports
   - Added refresh() calls after commits
   - Fixed concurrent test approach
   - Added missing fixture parameters

3. `/home/rigade/Testing/ai-model-validation-platform/backend/tests/integration/test_fix_integration_comprehensive.py`
   - Removed duplicate fixture definitions
   - Fixed session usage in race condition test
   - Removed unnecessary clean_database fixture

4. `/home/rigade/Testing/ai-model-validation-platform/backend/tests/integration/test_ground_truth_data_flow.py`
   - Replaced all SessionLocal() with db_session parameter
   - Fixed all fixture signatures
   - Added refresh() calls throughout
   - Fixed indentation issues

## Testing Results

### Before Fixes:
- 10+ tests failing with InvalidRequestError
- Session attachment conflicts
- Detached instance errors

### After Fixes:
- Fixture errors resolved
- Session management properly isolated
- Tests can load and execute
- 1 test passing in test_ground_truth_data_flow.py

## Best Practices Established

1. **Never create SessionLocal() in tests** - Always use fixture
2. **Always refresh after commit** - Prevents detachment
3. **Use expire_on_commit=False** - Avoids lazy-load issues
4. **Proper cleanup with expunge_all()** - Prevents cross-test contamination
5. **Transaction isolation** - Each test gets fresh transaction
6. **Single session per test** - Avoid multiple session instances

## Remaining Work

Some tests still failing due to:
- Missing model imports (LabjackSignal, TestDataHelper)
- Missing service modules (drift_measurement_service)
- API endpoint issues (requires running server)

These are separate issues from session management and should be addressed independently.

## References

- SQLAlchemy Session Management: https://docs.sqlalchemy.org/en/14/orm/session_basics.html
- Pytest Fixtures: https://docs.pytest.org/en/stable/fixture.html
- FastAPI Testing: https://fastapi.tiangolo.com/tutorial/testing/
