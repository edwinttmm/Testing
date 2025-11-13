# Test Execution Guide

## Quick Start

This guide provides step-by-step instructions for running all test suites created for the AI Model Validation Platform bug fixes.

---

## Prerequisites

### Backend Tests
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Activate virtual environment
source venv/bin/activate

# Verify pytest is installed
python -m pytest --version

# If pytest not installed:
pip install pytest pytest-cov pytest-asyncio
```

### Frontend Tests
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Install dependencies (if not already installed)
npm install

# Install test dependencies
npm install --save-dev @testing-library/react @testing-library/jest-dom @testing-library/user-event jest ts-jest @types/jest
```

---

## Running Backend Tests

### 1. Detection Window Grace Period Tests
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate

# Run all grace period tests
python -m pytest tests/test_detection_window_grace_period.py -v

# Run specific test
python -m pytest tests/test_detection_window_grace_period.py::TestDetectionWindowGracePeriod::test_grace_period_accepts_early_signals -v

# Run with detailed output
python -m pytest tests/test_detection_window_grace_period.py -vv --tb=long
```

**Expected Output:**
```
tests/test_detection_window_grace_period.py::TestDetectionWindowGracePeriod::test_grace_period_accepts_early_signals PASSED
tests/test_detection_window_grace_period.py::TestDetectionWindowGracePeriod::test_sequence_elapsed_time_initialization PASSED
tests/test_detection_window_grace_period.py::TestDetectionWindowGracePeriod::test_multi_video_timing_accuracy PASSED
...
============== 14 passed in 1.8s ==============
```

### 2. Dual-Evaluation Architecture Tests
```bash
# Run all dual-evaluation tests
python -m pytest tests/test_dual_evaluation_architecture.py -v

# Run with coverage
python -m pytest tests/test_dual_evaluation_architecture.py --cov=services --cov-report=term-missing
```

**Expected Output:**
```
tests/test_dual_evaluation_architecture.py::TestDualEvaluationArchitecture::test_high_accuracy_good_latency_both_pass PASSED
tests/test_dual_evaluation_architecture.py::TestDualEvaluationArchitecture::test_high_accuracy_slow_latency_overall_fail PASSED
...
============== 8 passed in 1.2s ==============
```

### 3. End-to-End Integration Tests
```bash
# Run integration tests
python -m pytest tests/integration/test_end_to_end_timing_fixes.py -v

# Run with output capture disabled (see print statements)
python -m pytest tests/integration/test_end_to_end_timing_fixes.py -v -s
```

**Expected Output:**
```
tests/integration/test_end_to_end_timing_fixes.py::TestEndToEndTimingFixes::test_complete_timing_flow PASSED
tests/integration/test_end_to_end_timing_fixes.py::TestEndToEndTimingFixes::test_multi_video_sequence_timing PASSED

✅ End-to-End Test Results:
   Sequence Start: 8.7s
   Video Start: 10.5s
   Grace Detections: 1
   True Positives: 3
   False Positives: 0
   False Negatives: 2
   F1 Score: 0.75
   Avg Latency: 85.0ms
   Accuracy Result: PASS
   Latency Result: PASS
   Overall Result: PASS

============== 2 passed in 3.5s ==============
```

### 4. Run All Backend Tests
```bash
# Run all tests with coverage
python -m pytest tests/ -v --cov=services --cov=models --cov-report=html --cov-report=term

# Generate coverage report
# Open: backend/htmlcov/index.html
```

---

## Running Frontend Tests

### 1. Video Player Component Tests
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Run all SequentialVideoPlayer tests
npm test -- SequentialVideoPlayer.test.tsx

# Run with coverage
npm test -- --coverage --watchAll=false

# Run specific test
npm test -- -t "should clean up all event listeners when video playback fails"

# Run with verbose output
npm test -- SequentialVideoPlayer.test.tsx --verbose
```

**Expected Output:**
```
PASS src/components/__tests__/SequentialVideoPlayer.test.tsx
  SequentialVideoPlayer - Critical Bug Fixes
    Memory Leak Prevention - Event Listener Cleanup
      ✓ should clean up all event listeners when video playback fails (45ms)
      ✓ should not accumulate listeners across multiple video loads (67ms)
      ✓ should use AbortController to clean up waitForPlaybackStart listeners (52ms)
    Race Condition Prevention - waitForPlaybackStart
      ✓ should reuse existing promise when waitForPlaybackStart called concurrently (38ms)
      ✓ should clear promise ref after playback starts (29ms)
      ✓ should handle rapid consecutive calls without creating duplicate listeners (41ms)
    Autoplay Blocking Detection
      ✓ should detect NotAllowedError and show user-friendly message (33ms)
      ✓ should provide actionable guidance when autoplay is blocked (36ms)
      ✓ should distinguish NotAllowedError from other play errors (31ms)
    Timestamp Consistency
      ✓ should use high-precision timestamps for all timing functions (42ms)
      ✓ should maintain timestamp consistency across video transitions (48ms)
      ✓ should calculate sequenceElapsedTime consistently (37ms)
    Integration - All Fixes Working Together
      ✓ should handle full playback lifecycle without memory leaks or race conditions (89ms)

Test Suites: 1 passed, 1 total
Tests:       13 passed, 13 total
Time:        2.345s
```

---

## Coverage Reports

### Backend Coverage
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate

# Generate HTML coverage report
python -m pytest tests/ --cov=services --cov=models --cov-report=html

# View report
# Open: backend/htmlcov/index.html

# Generate XML for CI/CD
python -m pytest tests/ --cov=services --cov=models --cov-report=xml

# Console summary
python -m pytest tests/ --cov=services --cov=models --cov-report=term-missing
```

### Frontend Coverage
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Generate coverage report
npm test -- --coverage --watchAll=false

# View report
# Open: frontend/coverage/lcov-report/index.html
```

---

## Troubleshooting

### Backend Tests

**Issue**: `ModuleNotFoundError: No module named 'pytest'`
```bash
# Solution: Install pytest in virtual environment
cd backend
source venv/bin/activate
pip install pytest pytest-cov pytest-asyncio
```

**Issue**: `ImportError: cannot import name 'X' from 'models'`
```bash
# Solution: Ensure PYTHONPATH includes backend directory
export PYTHONPATH="${PYTHONPATH}:/home/rigade/Testing/ai-model-validation-platform/backend"
```

**Issue**: Database errors
```bash
# Solution: Tests use in-memory SQLite, but check models
# Verify models.py and database.py are in backend directory
ls -la /home/rigade/Testing/ai-model-validation-platform/backend/models.py
```

### Frontend Tests

**Issue**: `Cannot find module '@testing-library/react'`
```bash
# Solution: Install testing libraries
npm install --save-dev @testing-library/react @testing-library/jest-dom
```

**Issue**: `SyntaxError: Unexpected token 'export'`
```bash
# Solution: Update Jest config for ES modules
# Check: frontend/jest.config.js exists and has correct transform
```

**Issue**: Mock errors
```bash
# Solution: Verify mock setup in setupTests.ts
# Check: frontend/src/setupTests.ts exists
```

---

## Continuous Integration

### GitHub Actions Example
```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          cd backend
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v --cov=services --cov=models --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run tests
        run: |
          cd frontend
          npm test -- --coverage --watchAll=false

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./frontend/coverage/coverage-final.json
```

---

## Test Data Inspection

### Backend Test Database
```bash
# Tests use in-memory SQLite by default
# To inspect test data during debugging:

# 1. Modify conftest.py to use file-based SQLite
# Change: "sqlite:///:memory:"
# To: "sqlite:///test_database.db"

# 2. Run tests
python -m pytest tests/test_detection_window_grace_period.py -v

# 3. Inspect database
sqlite3 test_database.db
> .tables
> SELECT * FROM videos;
> SELECT * FROM detection_events;
```

### Frontend Component State
```bash
# Use React DevTools browser extension
# Or add debug output in tests:

# In test file:
import { screen, debug } from '@testing-library/react';

// In test:
debug(); // Prints current DOM
screen.debug(); // Prints specific element
```

---

## Performance Profiling

### Backend Tests
```bash
# Profile test execution
python -m pytest tests/ --profile

# Or use pytest-benchmark
pip install pytest-benchmark
# Add benchmark fixtures to tests
```

### Frontend Tests
```bash
# Run with verbose timing
npm test -- --verbose

# Use Jest performance tools
npm test -- --detectLeaks
```

---

## Manual Test Verification

### Backend Grace Period Logic
```python
# Quick manual test in Python REPL
cd backend
source venv/bin/activate
python

>>> from models import Video
>>> video = Video(start_time=10.5, sequence_elapsed_time=1.8)
>>> sequence_start = video.start_time - video.sequence_elapsed_time
>>> grace_period = 2.0
>>> window_start = sequence_start + video.sequence_elapsed_time - grace_period
>>> print(f"Window start: {window_start}s (expected: 8.5s)")
Window start: 8.5s (expected: 8.5s)
```

### Frontend Video Player
```javascript
// In browser console during test execution
// Add to SequentialVideoPlayer.tsx temporarily:

console.log('Video event listeners:', videoEventListeners.size);
console.log('Timestamp:', performance.now());
```

---

## Success Checklist

Before merging fixes, verify:

- [ ] All backend tests pass (24 tests)
- [ ] All frontend tests pass (13 tests)
- [ ] Coverage ≥ 85% overall
- [ ] No console errors in test output
- [ ] Coverage reports generated
- [ ] CI/CD pipeline passes
- [ ] Manual verification completed
- [ ] Documentation updated

---

## Quick Reference

### Run Everything
```bash
# Backend
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate
pytest tests/ -v --cov=. --cov-report=html

# Frontend
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm test -- --coverage --watchAll=false
```

### View Coverage
```bash
# Backend: open backend/htmlcov/index.html
# Frontend: open frontend/coverage/lcov-report/index.html
```

### Test Files Created
1. `frontend/src/components/__tests__/SequentialVideoPlayer.test.tsx` (13 tests)
2. `backend/tests/test_detection_window_grace_period.py` (14 tests)
3. `backend/tests/test_dual_evaluation_architecture.py` (8 tests)
4. `backend/tests/integration/test_end_to_end_timing_fixes.py` (2 tests)

**Total**: 37 tests across 4 files

---

**Last Updated**: 2025-11-11
**Status**: ✅ Ready for Execution
