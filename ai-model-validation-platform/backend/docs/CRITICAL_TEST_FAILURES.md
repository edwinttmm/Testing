# Critical Test Failures - Detailed Analysis
**Generated:** 2025-11-20
**Status:** NO-GO - Collection Blockers Prevent Full Assessment

---

## Overview

This document catalogs **critical failures** preventing successful test execution. All failures are categorized by priority and include specific remediation steps.

---

## P0 (Blocker) - Collection Errors

### Category A: Missing pytest Import (25 Files)

**Severity:** BLOCKER
**Impact:** Tests cannot collect, preventing execution
**Error:** `NameError: name 'pytest' is not defined`

#### Affected Files:
1. `tests/services/test_callback_memory_leak.py`
2. `tests/services/test_clock_sync_service.py`
3. `tests/services/test_drift_integration.py`
4. `tests/services/test_drift_measurement_service.py`
5. `tests/services/test_timestamp_compensation_service.py`
6. `tests/integration/test_end_to_end_timing_fixes.py`
7. `tests/integration/test_video_lifecycle_e2e.py`
8. `tests/unit/test_drift_measurement_service.py`
9. `tests/hil-detection-pipeline/test_labjack_connection.py`
10. `tests/hil-detection-pipeline/test_stream_mode_integration.py`
11. `tests/hil-detection-pipeline/test_websocket_events.py`
12. `tests/hil_labjack/test_monitoring_service_isolation.py`
13. `tests/hil_labjack/test_realtime_monitoring.py`
14. `tests/hil_labjack/test_session_integration.py`
15. `tests/deprecated/test_integration_production_fixes.py`
16. `tests/deprecated/test_latency_validation_service.py`
17. `tests/test_performance_benchmarks.py`
18. `tests/test_performance_compatibility.py`
19. `tests/test_phase4_solves_all_issues.py`
20. `tests/test_session_completion_logic.py`
21. `tests/test_timing_fixes_integration.py`
22. `tests/test_timing_integration.py`
23. `tests/test_unified_latency_field.py`
24. `tests/test_validation_engine.py`
25. `tests/test_video_sequence_orchestrator.py`

**Error Message:**
```
ERROR tests/services/test_callback_memory_leak.py - NameError: name 'pytest' is not defined
```

**Root Cause:**
Files use pytest decorators (`@pytest.fixture`, `@pytest.mark.asyncio`, etc.) without importing pytest.

**Fix:**
Add `import pytest` at the top of each file, after docstring but before any pytest usage.

**Example Fix:**
```python
"""
Test file docstring
"""
import pytest  # ADD THIS LINE
from unittest.mock import Mock

@pytest.fixture  # This now works
def my_fixture():
    pass
```

**Automated Fix:**
```bash
# Run this script to fix all affected files
for file in tests/services/test_callback_memory_leak.py \
            tests/services/test_clock_sync_service.py \
            tests/services/test_drift_integration.py \
            # ... (add all files)
do
    # Add import after first docstring
    sed -i '/"""/a import pytest' "$file"
done
```

---

### Category B: Module Import Errors (35 Files)

**Severity:** BLOCKER
**Impact:** Tests cannot collect due to missing modules
**Error:** `ModuleNotFoundError` or `ImportError`

#### Subcategory B1: LabJack Service Import Issues (15 files)

**Affected Files:**
1. `tests/test_backward_compatibility.py`
2. `tests/test_backward_compatibility_suite.py`
3. `tests/test_camera_integration.py`
4. `tests/test_hardware_integration_suite.py`
5. `tests/test_hil_hardware_validation.py`
6. `tests/test_hil_monitoring_integration.py`
7. `tests/test_labjack_hybrid_logging_system.py`
8. `tests/test_labjack_timing_workflow_comprehensive.py`
9. `tests/performance/test_labjack_performance_comprehensive.py`
10-15. (Additional labjack-related tests)

**Error Message:**
```
ModuleNotFoundError: No module named 'services.labjack_service_manager'
```

**Root Cause:**
Tests import from `services.labjack_service_manager` but conftest.py doesn't properly resolve the path. Services exist in both `/services/` and `/src/services/`, causing confusion.

**Fix Options:**

**Option 1 (Recommended): Standardize on src/services/**
```python
# Update imports in all test files
# FROM:
from services.labjack_service_manager import LabJackService
# TO:
from src.services.labjack_service_manager import LabJackService
```

**Option 2: Update conftest.py to prioritize /services/**
```python
# In conftest.py, ensure backend/services is first in path
services_dir = backend_root / "services"
if str(services_dir) not in sys.path:
    sys.path.insert(0, str(services_dir))
```

**Option 3: Create symlinks**
```bash
# Not recommended, but quick fix
cd /home/rigade/Testing/ai-model-validation-platform/backend
ln -s services/labjack_service_manager.py src/services/
```

#### Subcategory B2: Missing Test Dependencies (12 files)

**Affected Files:**
1. `tests/test_comprehensive_qa_validation.py`
2. `tests/test_crash_recovery.py`
3. `tests/test_detection_window_grace_period.py`
4. `tests/test_end_to_end_validation.py`
5-12. (Additional files with missing dependencies)

**Error Message:**
```
ImportError: cannot import name 'SomeClass' from 'module'
```

**Root Cause:**
Tests import classes or functions that don't exist or have been renamed/moved.

**Fix:**
Review each import error individually:
```bash
# Find what the test is trying to import
grep -n "^from\|^import" tests/test_comprehensive_qa_validation.py

# Check if module exists
find . -name "module_name.py"

# Update import or create missing module
```

#### Subcategory B3: Deprecated Test Files (8 files)

**Affected Files:**
1. `tests/deprecated/test_integration_production_fixes.py`
2. `tests/deprecated/test_latency_validation_service.py`
3. `tests/deprecated/test_video_timing_service.py`
4. `tests/deprecated/integration/test_ground_truth_e2e_integration.py`
5-8. (Other deprecated tests)

**Error Message:**
Various import errors for old/removed modules

**Root Cause:**
These tests are in `/deprecated/` folder but still being collected by pytest.

**Fix:**
Add pytest skip marker OR exclude from collection:

**Option 1: Skip deprecated tests**
```python
# At top of each deprecated file
import pytest
pytestmark = pytest.mark.skip(reason="Deprecated test file")
```

**Option 2: Exclude from pytest collection**
```ini
# In pytest.ini
[pytest]
norecursedirs = deprecated .git __pycache__
```

**Option 3: Delete deprecated tests**
```bash
# If truly deprecated and not needed
rm -rf tests/deprecated/
```

---

### Category C: SQLAlchemy Model Collection Issues (8 Files)

**Severity:** BLOCKER
**Impact:** pytest treats SQLAlchemy model as test class
**Error:** `sqlalchemy.exc.InvalidRequestError`

**Affected Files:**
1. `tests/test_compression_performance.py`
2. `tests/test_labjack_detection_workflow_validation.py`
3. `tests/test_labjack_timing_synchronization.py`
4. `tests/test_vru_integration_suite.py`
5-8. (Additional files with SQLAlchemy issues)

**Error Message:**
```
sqlalchemy.exc.InvalidRequestError: SQL expression, column, or mapped entity expected - got '<class 'models.TestSession'>'
```

**Root Cause:**
SQLAlchemy model class named `TestSession` is being collected by pytest as a test class because it starts with "Test".

**Warning from pytest:**
```
models.py:213: PytestCollectionWarning: cannot collect test class 'TestSession'
because it has a __init__ constructor
```

**Fix Options:**

**Option 1 (Recommended): Rename Model Class**
```python
# In models.py, line 213
# FROM:
class TestSession(Base):
    __tablename__ = "test_sessions"

# TO:
class ValidationSession(Base):  # or SessionModel, TestSessionModel, etc.
    __tablename__ = "test_sessions"  # table name can stay the same
```

**Option 2: Configure pytest to Ignore**
```ini
# In pytest.ini
[pytest]
python_classes = Test*[!Session]
```

**Option 3: Move Model to Different Module**
```bash
# Move TestSession to models/session.py
# Update all imports
```

**Impact of Fix:**
- Must update all references to `TestSession` throughout codebase
- Database table name can remain unchanged (`test_sessions`)
- Estimated 50-100 files to update

---

### Category D: Invalid Skip Markers (15 Files)

**Severity:** BLOCKER
**Impact:** Skip marker doesn't prevent import errors
**Error:** Import errors occur before skip takes effect

**Affected Files:**
1. `tests/test_camera_integration.py`
2. `tests/test_qa_validation_standalone.py`
3. `tests/test_vru_integration_suite.py`
4. `tests/integration/test_ground_truth_data_flow.py`
5. `tests/services/test_drift_monitoring_service.py`
6. `tests/deprecated/test_integration_production_fixes.py`
7. `tests/deprecated/test_video_timing_service.py`
8-15. (Additional files with improper skip markers)

**Error Pattern:**
```python
# Current (WRONG):
"""Test file docstring"""
import pytest
from some_module import SomethingThatDoesntExist  # ERROR OCCURS HERE

pytestmark = pytest.mark.skip(reason="Missing dependencies")  # Too late!
```

**Root Cause:**
`pytestmark` skip marker is placed AFTER imports. Python executes imports before reaching the skip marker, causing ModuleNotFoundError.

**Fix:**
Move `pytestmark` to TOP of file, immediately after docstring:

```python
# Corrected (RIGHT):
"""Test file docstring"""
import pytest

pytestmark = pytest.mark.skip(reason="Missing dependencies")  # Skip BEFORE imports

from some_module import SomethingThatDoesntExist  # This is skipped now
```

**Automated Fix:**
```bash
# Script to fix skip marker placement
for file in tests/test_camera_integration.py \
            tests/test_qa_validation_standalone.py \
            # ... (add all affected files)
do
    python << 'EOF'
import re
with open("$file", 'r') as f:
    content = f.read()

# Find and move pytestmark to top
# (implementation details...)
EOF
done
```

---

## P1 (Critical) - Test Execution Failures

### Category E: API Endpoint Not Found (12 Tests)

**Severity:** CRITICAL
**Impact:** Integration tests fail, endpoints may be missing
**Error:** `404 Not Found`

**Example Failures:**
```python
tests/test_frontend_integration.py::test_enhanced_test_execution_page_load FAILED
tests/test_frontend_integration.py::test_export_test_results_api_integration FAILED
tests/test_frontend_metrics_integration.py::test_api_endpoint_accessible FAILED
```

**Error Message:**
```
AssertionError: Expected status 200, got 404
Response: {"detail": "Not Found"}
```

**Root Cause:**
- API endpoints not registered in FastAPI app
- Incorrect URL paths in tests
- Missing router imports in main.py

**Fix:**
```python
# 1. Verify endpoint exists
grep -r "def enhanced_test_execution" src/api/

# 2. Check router is included in main.py
# In main.py:
from src.api import enhanced_test_endpoints
app.include_router(enhanced_test_endpoints.router)

# 3. Verify URL path matches
# Test expects: /api/enhanced-test-execution
# Router defines: /enhanced-test-execution
# Fix mismatch
```

---

### Category F: Database Timeout Errors (8 Tests)

**Severity:** CRITICAL
**Impact:** Tests hang and timeout
**Error:** `asyncio.TimeoutError` or `OperationalError: database is locked`

**Example Failures:**
```python
tests/test_error_scenarios_integration.py::test_database_timeout FAILED
tests/test_error_scenarios_integration.py::test_error_recovery_and_retry FAILED
```

**Error Message:**
```
asyncio.TimeoutError: Database operation timed out after 30s
```

**Root Cause:**
- Database connections not properly closed
- Tests running in parallel accessing same DB
- Missing transaction rollbacks

**Fix:**
```python
# Use fixtures with proper cleanup
@pytest.fixture
async def db_session():
    session = get_test_db_session()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()

# Use test-specific database
@pytest.fixture(scope="function")
def test_db():
    db_name = f"test_db_{uuid.uuid4()}"
    create_database(db_name)
    yield db_name
    drop_database(db_name)
```

---

### Category G: WebSocket Connection Failures (10 Tests)

**Severity:** CRITICAL
**Impact:** Real-time features untested
**Error:** `ConnectionRefusedError` or timeout

**Example Failures:**
```python
tests/test_frontend_integration.py::test_websocket_real_time_updates FAILED
tests/test_failure_scenarios.py::test_websocket_disconnect_during_video_start FAILED
```

**Error Message:**
```
ConnectionRefusedError: [Errno 111] Connection refused
Failed to connect to ws://localhost:8000/ws
```

**Root Cause:**
- WebSocket server not started in test environment
- Incorrect WS URL
- Missing event loop configuration

**Fix:**
```python
# Start test WebSocket server
@pytest.fixture(scope="module")
async def ws_server():
    app = create_app()
    server = await start_ws_server(app)
    yield server
    await server.close()

# Use test client with WebSocket support
from fastapi.testclient import TestClient
with TestClient(app) as client:
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
```

---

### Category H: Missing Test Data/Fixtures (15 Tests)

**Severity:** CRITICAL
**Impact:** Tests cannot run without required data
**Error:** `KeyError`, `AttributeError`, or assertion failures

**Example Failures:**
```python
tests/test_frontend_compatibility.py::test_empty_results_handling FAILED
tests/test_frontend_compatibility.py::test_missing_session_handling FAILED
```

**Error Message:**
```
KeyError: 'session_id'
AssertionError: Expected session data, got None
```

**Root Cause:**
- Missing pytest fixtures
- Test data not created
- Database seeds not applied

**Fix:**
```python
# Create comprehensive fixtures
@pytest.fixture
def sample_session(db_session):
    session = TestSession(
        id=1,
        name="Test Session",
        status="active"
    )
    db_session.add(session)
    db_session.commit()
    return session

@pytest.fixture
def sample_video(db_session, sample_session):
    video = Video(
        id=1,
        session_id=sample_session.id,
        filename="test.mp4"
    )
    db_session.add(video)
    db_session.commit()
    return video
```

---

## P2 (Important) - Performance and Stability

### Category I: Slow Tests (30+ Tests >5s)

**Severity:** IMPORTANT
**Impact:** Test suite takes too long
**Current:** 15-20 minutes for full suite
**Target:** <10 minutes

**Slow Tests:**
```
tests/test_failure_scenarios.py::test_hungarian_algorithm_50k_matrix - 12.3s
tests/test_performance_benchmarks.py::test_detection_throughput - 8.7s
tests/integration/test_video_lifecycle_e2e.py::test_complete_workflow - 15.2s
```

**Fix:**
1. Mock external dependencies (DB, APIs, hardware)
2. Use in-memory SQLite for tests
3. Parallelize with pytest-xdist: `pytest -n auto`
4. Skip slow tests by default: `@pytest.mark.slow`

---

### Category J: Flaky Tests (10-15 Tests)

**Severity:** IMPORTANT
**Impact:** Non-deterministic failures, CI/CD unreliable
**Pattern:** Tests pass/fail randomly

**Examples:**
```
tests/test_failure_scenarios.py::test_websocket_disconnect_during_video_start - Flaky
tests/test_error_scenarios_integration.py::test_concurrent_errors - Flaky
```

**Root Cause:**
- Race conditions
- Timing dependencies
- Shared state between tests

**Fix:**
```python
# Add retries for flaky tests
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_websocket_disconnect():
    ...

# Add explicit waits
async def wait_for_condition(condition, timeout=5):
    start = time.time()
    while time.time() - start < timeout:
        if await condition():
            return True
        await asyncio.sleep(0.1)
    return False
```

---

## Summary of Fixes Required

| Priority | Category | Files | Est. Hours | Status |
|----------|----------|-------|------------|--------|
| P0 | Missing pytest imports | 25 | 0.5 | Not Started |
| P0 | Module import errors | 35 | 3-5 | Not Started |
| P0 | SQLAlchemy model issues | 8 | 2-3 | Not Started |
| P0 | Invalid skip markers | 15 | 1 | Not Started |
| P1 | API endpoint failures | 12 | 2-4 | Not Started |
| P1 | Database timeouts | 8 | 2-3 | Not Started |
| P1 | WebSocket failures | 10 | 3-4 | Not Started |
| P1 | Missing test data | 15 | 4-6 | Not Started |
| P2 | Slow tests | 30+ | 5-8 | Not Started |
| P2 | Flaky tests | 10-15 | 4-6 | Not Started |

**Total Estimated Effort:** 27-41 hours (3.5-5 days of focused work)

---

## Next Actions

1. **Immediate (Today):**
   - Run automated script to add missing `import pytest` statements
   - Fix skip marker placement in 15 files
   - Total time: 2-3 hours

2. **Tomorrow:**
   - Resolve module import errors (standardize on src/services/)
   - Rename TestSession model to avoid pytest collision
   - Total time: 5-6 hours

3. **Day 3:**
   - Fix API endpoint registration issues
   - Create missing test fixtures
   - Total time: 6-8 hours

4. **Days 4-5:**
   - Fix database timeout issues
   - Resolve WebSocket test failures
   - Address slow/flaky tests
   - Total time: 12-16 hours

**After fixes:** Re-run full test suite and generate updated report.

---

**Report Generated By:** QA Testing Agent
**Date:** 2025-11-20 22:10 UTC
**Next Review:** After P0 fixes are complete
