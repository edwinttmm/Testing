# Integration Test Suite - README

## Overview

This directory contains automated integration tests for the AI Model Validation Platform's detection flow quality tracking features.

## Files

### 1. `integration_test.sh`
**Purpose:** Comprehensive end-to-end test suite
**Tests:** 10 automated tests covering complete detection flow
**Runtime:** ~10 seconds
**Exit Codes:**
- `0` - All tests passed
- `1` - One or more tests failed

**What It Tests:**
- ✅ Database schema has required columns
- ✅ Model definitions correct
- ✅ Session creation with quality fields
- ✅ Detection creation with quality fields
- ✅ Quality-based filtering
- ✅ Monitoring endpoints
- ✅ Security validation
- ✅ Metrics collection
- ⚠️ Dependencies present
- ⚠️ Service initialization

**Usage:**
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
./scripts/integration_test.sh
```

**Output:**
- Colored test results (green/red/yellow)
- Summary of passed/failed/warnings
- List of failures if any
- Exit code for CI/CD integration

---

### 2. `fix_integration_issues.sh`
**Purpose:** Automated fix for critical integration issues
**Runtime:** ~2 minutes (first run), ~30 seconds (subsequent)
**Exit Codes:**
- `0` - All fixes applied successfully
- `1` - Fix failed (manual intervention needed)

**What It Does:**
1. Creates Python virtual environment (if needed)
2. Installs all dependencies (including scipy)
3. Fixes migration chain references
4. Applies database migrations
5. Verifies schema correctness

**Usage:**
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
./scripts/fix_integration_issues.sh
```

**After Running:**
```bash
# Activate virtual environment
source venv/bin/activate

# Run tests to verify
./scripts/integration_test.sh

# Start server
python main.py
```

---

## Quick Start

### First Time Setup
```bash
# 1. Fix integration issues
./scripts/fix_integration_issues.sh

# 2. Verify everything works
./scripts/integration_test.sh

# 3. Start development
source venv/bin/activate
python main.py
```

### Regular Testing
```bash
# Run tests before committing
./scripts/integration_test.sh

# If tests fail, check the report
cat docs/END_TO_END_TEST_REPORT.md
```

---

## Test Categories

### Critical Tests (Must Pass)
1. **Database Schema** - Columns exist in actual database
2. **Session Creation** - Can create with quality fields
3. **Detection Creation** - Can create with validation flags
4. **Quality Filtering** - Can filter by usable_for_validation

### Important Tests (Should Pass)
5. **Model Definitions** - Code matches database
6. **Monitoring Router** - Endpoints load correctly
7. **Security Validation** - UUID and SQL injection protection
8. **Metrics Collection** - Accurate tracking

### Warning Tests (May Have Issues)
9. **Dependencies** - All packages installed
10. **Service Init** - Services can start

---

## Understanding Test Results

### ✅ PASS (Green)
Test completed successfully, feature working as expected.

### ❌ FAIL (Red)
Critical failure, feature broken. Check error message.

### ⚠️ WARN (Yellow)
Non-critical issue or expected limitation (e.g., SQLite pool monitoring).

---

## Common Issues and Fixes

### Issue: "table test_sessions has no column named timing_degraded"
**Cause:** Database migrations not applied
**Fix:** Run `./scripts/fix_integration_issues.sh`

### Issue: "ModuleNotFoundError: No module named 'scipy'"
**Cause:** Missing dependency
**Fix:** `pip install scipy` or run fix script

### Issue: "KeyError: 'add_video_id_to_detection_events'"
**Cause:** Broken migration chain
**Fix:** Run `./scripts/fix_integration_issues.sh`

### Issue: "'NullPool' object has no attribute 'size'"
**Cause:** SQLite doesn't support connection pooling
**Fix:** This is expected, warning only (not critical)

---

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Fix Integration Issues
        run: |
          cd backend
          ./scripts/fix_integration_issues.sh
      - name: Run Integration Tests
        run: |
          cd backend
          source venv/bin/activate
          ./scripts/integration_test.sh
```

---

## Test Data

Tests create and clean up their own data:
- Temporary test sessions
- Temporary detections
- Automatic cleanup after each test

**No manual cleanup needed.**

---

## Debugging Failed Tests

### 1. Run Tests with Verbose Output
```bash
bash -x ./scripts/integration_test.sh
```

### 2. Check Database State
```python
from database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
print(inspector.get_columns('test_sessions'))
```

### 3. Verify Migration Status
```bash
source venv/bin/activate
alembic current
alembic history
```

### 4. Check Service Logs
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
```

---

## Related Documentation

- **Full Test Report:** `../docs/END_TO_END_TEST_REPORT.md`
- **Quick Summary:** `../docs/INTEGRATION_TEST_SUMMARY.md`
- **Master Report:** `../docs/MASTER_INTEGRATION_REPORT.md`

---

## Support

If tests fail after running the fix script:
1. Check `docs/END_TO_END_TEST_REPORT.md` for detailed analysis
2. Verify virtual environment is activated
3. Ensure database file has write permissions
4. Check for conflicting Python versions

---

## Test Coverage

| Component | Tested | Status |
|-----------|--------|--------|
| Database Schema | ✅ | Complete |
| Model Definitions | ✅ | Complete |
| API Endpoints | ✅ | Complete |
| Security | ✅ | Complete |
| Metrics | ✅ | Complete |
| Quality Filtering | ✅ | Complete |
| Service Init | ✅ | Complete |
| Dependencies | ✅ | Complete |

**Overall Coverage:** ~85% of detection flow

---

*Last Updated: 2025-11-19*
*Test Suite Version: 1.0*
