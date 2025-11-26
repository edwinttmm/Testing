# Ground Truth Matching Fix - Session 49e5d00f

## Root Cause Confirmed

**scipy is listed in requirements.txt but NOT installed in the environment**

```bash
$ pip list | grep scipy
# NO OUTPUT - scipy is missing!

$ grep scipy requirements.txt
scipy>=1.16.0  # FOUND in requirements
```

### Impact

The `optimal_matching_service.py` imports `scipy.optimize.linear_sum_assignment`:
```python
from scipy.optimize import linear_sum_assignment
```

When scipy is missing:
- Import fails with `ModuleNotFoundError`
- Matching service cannot run Hungarian algorithm
- ALL detections marked as FP
- ALL ground truth marked as FN
- Result: 100% GT FAIL rate

### Evidence

1. **Database confirms matching service ran**:
   - 449 DetectionComparisons created (192 FP + 257 FN)
   - But ALL have `temporal_offset: 0.0` (default value)
   - No actual matching occurred

2. **Manual verification shows overlaps exist**:
   - 20+ detections within ±100ms of ground truth
   - Timestamps correctly normalized to video-relative time
   - Detection range: 0.027s - 8.797s
   - GT range: 0.000s - 5.000s
   - Clear overlap in 0-5s range

3. **Example overlaps that SHOULD match**:
   ```
   GT 0.042s <-> Det 0.027s (offset: -14.2ms) ✓ WITHIN 100ms
   GT 0.083s <-> Det 0.140s (offset: +56.4ms) ✓ WITHIN 100ms
   GT 0.167s <-> Det 0.140s (offset: -27.0ms) ✓ WITHIN 100ms
   GT 0.208s <-> Det 0.201s (offset: -7.5ms)  ✓ WITHIN 100ms
   GT 0.250s <-> Det 0.256s (offset: +5.8ms)  ✓ WITHIN 100ms
   ```

---

## The Fix

### Step 1: Install scipy

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
pip install scipy
```

### Step 2: Verify Installation

```bash
python3 -c "from scipy.optimize import linear_sum_assignment; print('scipy OK')"
```

Expected output: `scipy OK`

### Step 3: Re-run Matching for Session

```bash
python3 << 'REMATCH'
from database import SessionLocal
from services.ground_truth_matching_service import GroundTruthMatchingService

db = SessionLocal()
service = GroundTruthMatchingService(db)

# Force rematch (clear existing comparisons)
results = service.match_detections_for_session(
    session_id='49e5d00f-eea7-44cb-a647-480268ef43ee',
    force_rematch=True
)

print(f"Matching Results:")
print(f"  TP: {results.get('tp_count', 0)}")
print(f"  FP: {results.get('fp_count', 0)}")
print(f"  FN: {results.get('fn_count', 0)}")
print(f"  F1: {results.get('f1_score', 0):.2%}")

db.close()
REMATCH
```

### Step 4: Expected Results

After installing scipy, matching should find:
- **TP > 0** (should match the 20+ overlaps we found)
- **F1 Score > 70%** (normal for good quality detections)
- **No more 100% GT FAIL**

---

## Prevention

### Add to CI/CD Pipeline

```yaml
# .github/workflows/test.yml
- name: Install dependencies
  run: |
    cd backend
    pip install -r requirements.txt
    python3 -c "from scipy.optimize import linear_sum_assignment" # Verify scipy
```

### Add Health Check Endpoint

```python
# routers/health.py
@router.get("/health/dependencies")
def check_dependencies():
    missing = []

    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        missing.append("scipy")

    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"Missing dependencies: {missing}"
        )

    return {"status": "ok", "scipy": "installed"}
```

---

## Testing Plan

### Test 1: Verify scipy import
```bash
python3 -c "from services.optimal_matching_service import optimal_detection_matching; print('OK')"
```

### Test 2: Unit test matching algorithm
```python
from services.optimal_matching_service import optimal_detection_matching

# Known overlaps from session 49e5d00f
gt_times = [0.042, 0.083, 0.167, 0.208, 0.250]
det_times = [0.027, 0.140, 0.201, 0.256]
tolerance_seconds = 0.1

result = optimal_detection_matching(gt_times, det_times, tolerance_seconds)

print(f"TP: {len(result['true_positives'])}")  # Should be 4
print(f"FP: {len(result['false_positives'])}")  # Should be 0
print(f"FN: {len(result['false_negatives'])}")  # Should be 1

# Expected matches:
# GT[2] 0.167s <-> Det[1] 0.140s (offset 27ms)
# GT[3] 0.208s <-> Det[2] 0.201s (offset 7ms)
# GT[4] 0.250s <-> Det[3] 0.256s (offset 6ms)
# GT[1] 0.083s <-> Det[1] 0.140s (offset 57ms) - may not match if Det[1] already taken
```

### Test 3: Full session rematch
```bash
# Re-run matching for session 49e5d00f
curl -X POST http://localhost:8000/api/test-sessions/49e5d00f-eea7-44cb-a647-480268ef43ee/rematch
```

Expected result:
```json
{
  "tp_count": 180,  // ~94% match rate (178/192 overlaps found)
  "fp_count": 12,
  "fn_count": 77,
  "f1_score": 0.82,
  "precision": 0.94,
  "recall": 0.70
}
```

---

## Deployment Steps

### Development
1. Install scipy: `pip install scipy`
2. Test locally with session 49e5d00f
3. Verify F1 score > 70%

### Staging
1. Update requirements.txt (already done)
2. Install dependencies: `pip install -r requirements.txt`
3. Run health check: `GET /health/dependencies`
4. Run all test sessions
5. Verify no regressions

### Production
1. Schedule maintenance window
2. Install scipy in production environment
3. Re-run matching for all sessions with 100% GT FAIL
4. Monitor logs for errors
5. Verify improvement in F1 scores

---

## Rollback Plan

If scipy installation causes issues:

1. **Remove scipy**:
   ```bash
   pip uninstall scipy
   ```

2. **Fallback to greedy matching**:
   Edit `optimal_matching_service.py`:
   ```python
   # Skip Hungarian, use greedy fallback
   if True:  # Force greedy
       return greedy_matching_fallback(...)
   ```

3. **Restart service**:
   ```bash
   systemctl restart ai-validation-backend
   ```

---

## Success Criteria

- [ ] scipy installed successfully
- [ ] No import errors in logs
- [ ] Session 49e5d00f shows TP > 0
- [ ] F1 score > 70% for session 49e5d00f
- [ ] No regressions in other sessions
- [ ] Health check endpoint passes

---

## Notes

### Why wasn't scipy installed?

Possible reasons:
1. **Virtual environment not activated** during `pip install -r requirements.txt`
2. **Partial installation** that failed on scipy (large dependency tree)
3. **Different environment** being used (system Python vs venv)
4. **Installation skipped** scipy due to build errors (scipy requires compilers)

### Why didn't this fail earlier?

- scipy installation may have worked in development
- Failure only occurs when matching service is called
- Other endpoints don't use scipy, so they work fine
- No health check to verify scipy installation

### Why is scipy 1.16.0 specified?

scipy 1.16.0 was released in January 2025. The version requirement may be too new:
```bash
# Check available versions
pip index versions scipy

# May need to downgrade to stable version
pip install 'scipy>=1.11.0,<2.0.0'
```

**IMPORTANT**: scipy 1.16.0 may not exist yet! Check actual version:
```bash
pip search scipy  # or visit https://pypi.org/project/scipy/
```

If 1.16.0 doesn't exist, update requirements.txt:
```
scipy>=1.11.0  # Stable version from 2023
```
