# Quick Start - Scipy Setup

**Status**: ✅ Scipy 1.16.1 installed and verified

## TL;DR - Start Backend Now

```bash
# From backend directory
source venv/bin/activate
python3 scripts/startup_check.py
python3 app/main.py
```

## Common Commands

### Activate Virtual Environment
```bash
source venv/bin/activate
```

### Verify Scipy Works
```bash
python3 scripts/verify_scipy.py
```

### Check All Dependencies
```bash
python3 scripts/startup_check.py
```

### Run Integration Tests
```bash
python3 scripts/test_scipy_matching.py
```

### Automated Startup (Recommended)
```bash
# Check dependencies only
./scripts/activate_and_run.sh

# Start backend service
./scripts/activate_and_run.sh --start

# Run verification
./scripts/activate_and_run.sh --verify
```

## Quick Verification

### One-liner: Is scipy working?
```bash
venv/bin/python3 -c "from scipy.optimize import linear_sum_assignment; print('✓ OK')"
```

**Expected output**: `✓ OK`

### One-liner: Full test
```bash
venv/bin/python3 -c "import numpy as np; from scipy.optimize import linear_sum_assignment; cost_matrix = np.array([[4, 1, 3], [2, 0, 5], [3, 2, 2]]); row_ind, col_ind = linear_sum_assignment(cost_matrix); print(f'✓ SUCCESS: {len(row_ind)} matches')"
```

**Expected output**: `✓ SUCCESS: 3 matches`

## Troubleshooting

### Problem: "No module named 'scipy'"

```bash
# Solution 1: Activate venv
source venv/bin/activate

# Solution 2: Use venv python directly
venv/bin/python3 your_script.py
```

### Problem: "externally-managed-environment"

**This is expected!** Use the virtual environment:
```bash
source venv/bin/activate
# Now pip install works inside venv
```

### Problem: Services fail to start

```bash
# Run diagnostics
python3 scripts/startup_check.py

# If scipy missing in venv, reinstall
source venv/bin/activate
pip install scipy numpy
```

## File Locations

### Scripts
- `scripts/verify_scipy.py` - Scipy verification
- `scripts/startup_check.py` - Full dependency check
- `scripts/test_scipy_matching.py` - Integration tests
- `scripts/activate_and_run.sh` - Automated startup

### Documentation
- `docs/scipy_installation.md` - Full installation guide
- `docs/SCIPY_SOLUTION_REPORT.md` - Complete solution report
- `docs/QUICK_START_SCIPY.md` - This file

### Services Using Scipy
- `services/ground_truth_matching_service.py` - Ground truth matching
- `services/optimal_matching_service.py` - Hungarian algorithm

## Environment Info

```
Python: 3.12.3
Scipy: 1.16.1
Numpy: 2.2.6
Virtual Environment: /backend/venv
```

## CI/CD Quick Setup

```yaml
# .github/workflows/backend.yml
- name: Setup and verify scipy
  run: |
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python3 scripts/startup_check.py
```

## Docker Quick Setup

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "app/main.py"]
```

## Requirements.txt Entry

```
scipy>=1.10.0,<2.0.0
numpy>=1.24.0,<3.0.0
```

## Need Help?

1. **Check status**: `python3 scripts/startup_check.py`
2. **Run tests**: `python3 scripts/test_scipy_matching.py`
3. **Read docs**: `docs/scipy_installation.md`
4. **Full report**: `docs/SCIPY_SOLUTION_REPORT.md`

## Success Checklist

- [ ] Virtual environment activated
- [ ] `python3 scripts/verify_scipy.py` passes
- [ ] `python3 scripts/startup_check.py` passes
- [ ] `python3 scripts/test_scipy_matching.py` passes (5/5)
- [ ] Backend starts without scipy errors

If all checked, you're ready to go! ✅
