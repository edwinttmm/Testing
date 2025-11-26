# Quick Start Guide - Per-Video Monitoring Tests

## Run Tests Immediately

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Install test dependencies (if not already installed)
pip install pytest pytest-asyncio pytest-benchmark pytest-cov

# Run all video lifecycle tests
pytest tests/integration/test_video_lifecycle_e2e.py \
       tests/unit/test_video_lifecycle_orchestrator.py \
       tests/unit/test_drift_measurement_service.py -v
```

## What Gets Tested

### ✅ Complete Workflow
- Video starts → LabJack monitors → Detections → Video ends
- Drift measured at each stage
- Ground truth matching with compensation
- Results evaluation

### ✅ Per-Video Drift Tracking
- Each video gets independent drift measurement
- No cross-contamination between videos
- Sequential video support

### ✅ Error Handling
- LabJack timeout recovery
- High drift alerting (>500ms)
- Graceful degradation

### ✅ Performance
- <100ms overhead per video lifecycle
- <10ms per detection (tested with 1000 detections)

## Test Files

| File | Tests | Lines | Description |
|------|-------|-------|-------------|
| `tests/integration/test_video_lifecycle_e2e.py` | 7 E2E | 813 | Full workflow validation |
| `tests/unit/test_video_lifecycle_orchestrator.py` | 20+ | 553 | Orchestrator unit tests |
| `tests/unit/test_drift_measurement_service.py` | 25+ | 509 | Drift service unit tests |

**Total**: 52+ tests, 1,875 lines of test code

## Quick Test Commands

```bash
# Single integration test
pytest tests/integration/test_video_lifecycle_e2e.py::TestVideoLifecycleE2E::test_single_video_complete_workflow -v

# All orchestrator unit tests
pytest tests/unit/test_video_lifecycle_orchestrator.py -v

# All drift service unit tests
pytest tests/unit/test_drift_measurement_service.py -v

# Performance benchmarks only
pytest tests/integration/test_video_lifecycle_e2e.py::TestVideoLifecyclePerformance --benchmark-only

# With coverage report
pytest tests/integration/ tests/unit/ \
  --cov=services.video_sequence_orchestrator \
  --cov=services.drift_measurement_service \
  --cov-report=html
```

## Expected Results

All tests should pass with output like:
```
tests/integration/test_video_lifecycle_e2e.py::TestVideoLifecycleE2E::test_single_video_complete_workflow PASSED
tests/integration/test_video_lifecycle_e2e.py::TestVideoLifecycleE2E::test_multi_video_sequential_workflow PASSED
...
===== 52 passed in 12.34s =====
```

## If Tests Fail

### Common Issues

1. **Missing Dependencies**
   ```bash
   pip install pytest pytest-asyncio pytest-benchmark pytest-cov
   ```

2. **Import Errors**
   ```bash
   # Make sure you're in the backend directory
   cd /home/rigade/Testing/ai-model-validation-platform/backend
   export PYTHONPATH=$PYTHONPATH:$(pwd)
   ```

3. **Database Issues**
   - Tests use in-memory SQLite
   - Automatically cleaned up after each test
   - No manual cleanup needed

### Debug Mode

```bash
# Run with verbose output
pytest tests/ -v -s --log-cli-level=DEBUG
```

## Coverage Report

After running tests with coverage:
```bash
# View HTML report
firefox htmlcov/index.html
# or
google-chrome htmlcov/index.html
```

Target coverage:
- VideoSequenceOrchestrator: >90%
- DriftMeasurementService: >95%

## Documentation

- **Detailed Guide**: `tests/docs/VIDEO_LIFECYCLE_TEST_SUITE.md`
- **Summary**: `tests/docs/TEST_SUITE_SUMMARY.md`
- **This File**: Quick start reference

## Next Steps After Tests Pass

1. ✅ Review coverage report
2. ✅ Fix any failing tests
3. ✅ Add tests to CI/CD pipeline
4. ✅ Run tests before each deployment
5. ✅ Add hardware-in-the-loop tests for real LabJack

---

**Ready to test?** Just run:
```bash
pytest tests/integration/test_video_lifecycle_e2e.py tests/unit/ -v
```
