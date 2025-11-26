# Integration Testing Guide - Fix Validation
**Date**: 2025-11-19
**Purpose**: Validate all fixes (FIX-1 through FIX-4) work together correctly

---

## Quick Start

### 1. Install Test Dependencies

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Activate virtual environment
source venv/bin/activate  # or your venv path

# Install test requirements
pip install pytest pytest-asyncio pytest-mock
```

### 2. Run All Integration Tests

```bash
# Run complete integration test suite
pytest tests/integration/test_fix_integration_comprehensive.py -v -s

# Run specific test
pytest tests/integration/test_fix_integration_comprehensive.py::TestFixIntegration::test_normal_flow_all_fixes -v -s

# Run with coverage
pytest tests/integration/test_fix_integration_comprehensive.py --cov=services --cov-report=html
```

### 3. Interpret Results

**Expected Output**:
```
tests/integration/test_fix_integration_comprehensive.py::TestFixIntegration::test_normal_flow_all_fixes PASSED [16%]
✅ TEST 1 PASSED: Normal flow with all fixes

tests/integration/test_fix_integration_comprehensive.py::TestFixIntegration::test_session_race_condition PASSED [33%]
✅ TEST 2 PASSED: Race condition handled gracefully

tests/integration/test_fix_integration_comprehensive.py::TestFixIntegration::test_timing_service_exception PASSED [50%]
✅ TEST 3 PASSED: Timing service exception handled

tests/integration/test_fix_integration_comprehensive.py::TestFixIntegration::test_database_connection_lost PASSED [66%]
✅ TEST 4 PASSED: Database failure handled gracefully

tests/integration/test_fix_integration_comprehensive.py::TestFixIntegration::test_concurrent_sessions PASSED [83%]
✅ TEST 5 PASSED: Concurrent sessions isolated correctly

tests/integration/test_fix_integration_comprehensive.py::TestFixIntegration::test_multi_video_sequence PASSED [100%]
✅ TEST 6 PASSED: Multi-video sequence maintains session ID

==================== 6 passed in 5.23s ====================
```

---

## Test Breakdown

### Test 1: Normal Flow (Happy Path)
**What it tests**: All fixes working in ideal conditions
**Validates**:
- ✅ FIX-1: Event signaled immediately
- ✅ FIX-2: Primary session ID used
- ✅ FIX-3: Session verification passes
- ✅ FIX-4: No retry needed (session visible)

**Pass Criteria**:
- Monitor starts within 500ms
- Detection saved to correct session
- Timing data initialized
- No errors or warnings

### Test 2: Session Race Condition
**What it tests**: PostgreSQL MVCC isolation handling
**Validates**:
- ✅ FIX-1: Event signaled even if session not found
- ✅ FIX-3: Graceful degradation to fallback timing
- ✅ FIX-4: Retry logic attempts to find session

**Pass Criteria**:
- Monitor doesn't crash
- Event signaled within 100ms
- Detection saved (with fallback timing)
- Retry attempts logged

### Test 3: Timing Service Exception
**What it tests**: Robustness to timing failures
**Validates**:
- ✅ FIX-1: Event signaled despite exception
- Monitor continues operating
- Detection saved with fallback

**Pass Criteria**:
- No crash or hang
- Exception logged
- Detection data preserved
- Fallback timestamp used

### Test 4: Database Connection Lost
**What it tests**: Resilience to transient DB failures
**Validates**:
- Error handling graceful
- Monitor continues running
- System recovers after DB restored

**Pass Criteria**:
- No crash or exception
- Error logged
- Second detection succeeds

### Test 5: Concurrent Sessions
**What it tests**: Session isolation and connection pool
**Validates**:
- ✅ FIX-2: No session ID confusion
- Each session isolated
- Connection pool stable

**Pass Criteria**:
- All 5 sessions start
- No cross-session contamination
- Connection pool not exhausted

### Test 6: Multi-Video Sequence
**What it tests**: Session ID consistency across videos
**Validates**:
- ✅ FIX-2: Primary session ID throughout
- Detections from all videos saved
- Timing accurate per video

**Pass Criteria**:
- Single session ID used
- Detections from 3 videos
- All linked to primary session

---

## Troubleshooting

### Test Failures

#### "Monitor should start successfully"
**Cause**: Monitor initialization failed
**Check**:
```bash
# Verify LabJack service available
python3 -c "from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor; print('OK')"

# Check logs
tail -f logs/backend.log | grep "Monitor"
```

#### "Detection should be saved"
**Cause**: Detection callback not triggered
**Check**:
```python
# Enable verbose logging
import logging
logging.getLogger('services.dedicated_labjack_monitor').setLevel(logging.DEBUG)
```

#### "Event should be signaled"
**Cause**: FIX-1 not applied correctly
**Check**:
```bash
# Verify FIX-1 is in code
grep -A 5 "timing_ready_event.set()" services/dedicated_labjack_monitor.py
# Should see it near line 502
```

### Database Issues

#### "SessionLocal not found"
```bash
# Check database.py exists
ls -la database.py

# Verify imports
python3 -c "from database import SessionLocal; print('OK')"
```

#### "OperationalError: (psycopg2.OperationalError)"
```bash
# Check PostgreSQL running
sudo systemctl status postgresql

# Test connection
psql -U postgres -c "SELECT 1;"
```

### Import Errors

#### "ModuleNotFoundError: No module named 'services'"
```bash
# Ensure PYTHONPATH includes backend
export PYTHONPATH=/home/rigade/Testing/ai-model-validation-platform/backend:$PYTHONPATH

# Or add to pytest
pytest --pythonpath=/home/rigade/Testing/ai-model-validation-platform/backend tests/integration/
```

---

## Advanced Testing

### Run with Different Isolation Levels

```python
# In database.py, change isolation level:
engine = create_engine(
    DATABASE_URL,
    isolation_level="SERIALIZABLE"  # Test with stricter isolation
)
```

### Stress Test with More Sessions

```python
# Modify test_concurrent_sessions
for i in range(20):  # Increase from 5 to 20
    session_id = create_session(f"stress-test-{i}")
    # ...
```

### Test with Real LabJack Hardware

```python
# Remove mock, use real hardware
@pytest.fixture
def real_labjack(self):
    # Ensure LabJack connected via USB
    import subprocess
    result = subprocess.run(['lsusb'], capture_output=True, text=True)
    assert 'LabJack' in result.stdout, "LabJack not connected"
    yield None
```

---

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9

      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio pytest-mock
          pip install -r requirements.txt

      - name: Run integration tests
        run: |
          pytest tests/integration/test_fix_integration_comprehensive.py -v

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## Performance Benchmarks

### Expected Timings

| Test | Expected Duration | Max Duration |
|------|------------------|--------------|
| Test 1 (Normal Flow) | 0.5s | 1.0s |
| Test 2 (Race Condition) | 1.0s | 2.0s |
| Test 3 (Exception) | 0.5s | 1.0s |
| Test 4 (DB Lost) | 0.8s | 1.5s |
| Test 5 (Concurrent) | 2.0s | 4.0s |
| Test 6 (Multi-Video) | 1.5s | 3.0s |

### Monitoring Test Performance

```bash
# Run with duration tracking
pytest tests/integration/ --durations=10

# Check slowest tests
pytest tests/integration/ -v --durations=0 | sort -k2 -n
```

---

## Success Metrics

After running full test suite, verify:

- [ ] ✅ All 6 integration tests pass
- [ ] ✅ 0 regression tests fail
- [ ] ✅ Total duration < 10 seconds
- [ ] ✅ No database connection leaks
- [ ] ✅ No memory leaks (check with `memory_profiler`)
- [ ] ✅ Logs show expected warnings, no unexpected errors

---

## Next Steps After Tests Pass

1. **Deploy to Staging**
   ```bash
   # Apply fixes to staging environment
   git checkout staging
   git merge feature/fix-integration
   git push origin staging
   ```

2. **Run Real Test Session**
   - Start backend on staging
   - Create test session via UI
   - Monitor for 10 minutes
   - Verify detections saved

3. **Monitor Production Metrics**
   ```python
   # Key metrics to watch
   - session_success_rate > 95%
   - detection_save_rate > 99%
   - timing_timeout_rate < 2%
   - connection_pool_usage < 80%
   ```

4. **Deploy to Production** (if staging successful)
   ```bash
   git checkout main
   git merge staging
   git tag v2.1.0-fixes
   git push origin main --tags
   ```

---

## Support & Debugging

### Enable Debug Logging

```python
# In main.py or conftest.py
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('services.dedicated_labjack_monitor').setLevel(logging.DEBUG)
logging.getLogger('services.video_timing_service').setLevel(logging.DEBUG)
```

### Capture Test Logs

```bash
# Run tests with log capture
pytest tests/integration/ -v -s --log-cli-level=DEBUG 2>&1 | tee test_output.log
```

### Interactive Debugging

```bash
# Drop into debugger on failure
pytest tests/integration/ --pdb

# Or use breakpoint() in test code
def test_something():
    breakpoint()  # Execution pauses here
    # ...
```

---

## Contact

**Questions?** See detailed analysis in:
- `/docs/INTEGRATION_TESTING_AGENT5_ANALYSIS.md`
- `/docs/DEFINITIVE_FIXES_PACKAGE.md`
- `/docs/AGENT_SWARM_FINAL_ANALYSIS.md`

**Issues?** Check troubleshooting section above or review logs.

---

**Test Suite Version**: 1.0
**Last Updated**: 2025-11-19
**Maintained By**: Agent 5 (QA & Integration Testing)
