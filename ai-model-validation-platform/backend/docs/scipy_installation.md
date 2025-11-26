# Scipy Installation Guide

## Overview

The AI Model Validation Platform requires **scipy** for advanced matching algorithms, specifically the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) used in ground truth matching services.

## Current Status

- **System Python**: scipy NOT installed (externally-managed-environment restriction)
- **Virtual Environment**: scipy 1.16.1 installed at `/backend/venv`
- **Solution**: Use virtual environment for all backend operations

## Quick Start

### Activate Virtual Environment

```bash
# From backend directory
source venv/bin/activate

# Verify scipy is available
python3 -c "from scipy.optimize import linear_sum_assignment; print('OK')"
```

### Run Verification Script

```bash
# With venv activated
python3 scripts/verify_scipy.py

# Or directly using venv python
venv/bin/python3 scripts/verify_scipy.py
```

## Installation Options

### Option 1: Virtual Environment (Recommended)

**Advantages:**
- Isolated dependencies
- No system conflicts
- Production best practice
- Easy to replicate

**Setup:**
```bash
# Create virtual environment (already done)
python3 -m venv venv

# Activate
source venv/bin/activate

# Install scipy
pip3 install scipy numpy

# Verify
python3 scripts/verify_scipy.py
```

**Usage in Production:**
```bash
# Always activate venv before running services
source venv/bin/activate
python3 app/main.py

# Or use venv python directly
venv/bin/python3 app/main.py
```

### Option 2: System-Wide Installation (Not Recommended)

**Only if you cannot use virtual environment:**

```bash
# Override externally-managed restriction (use with caution)
pip3 install --break-system-packages scipy

# This is NOT recommended for production systems
```

### Option 3: Docker Container (Production Alternative)

**For production deployments:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# scipy will be installed in container environment
COPY . .

CMD ["python", "app/main.py"]
```

## Services Requiring Scipy

### 1. Ground Truth Matching Service
**File**: `app/services/ground_truth_matching_service.py`

**Functions using scipy:**
- `match_predictions_to_ground_truth()` - Hungarian algorithm
- `_compute_distance_matrix()` - Cost matrix calculation

### 2. Optimal Matching Service
**File**: `app/services/optimal_matching_service.py`

**Functions using scipy:**
- `find_optimal_matching()` - Linear sum assignment
- `compute_matching_metrics()` - Performance analysis

## Verification

### Manual Verification

```python
# Test scipy import
python3 -c "import scipy; print(f'scipy {scipy.__version__}')"

# Test linear_sum_assignment
python3 -c "from scipy.optimize import linear_sum_assignment; print('OK')"

# Test with sample data
python3 << 'EOF'
import numpy as np
from scipy.optimize import linear_sum_assignment

cost_matrix = np.array([[4, 1, 3], [2, 0, 5], [3, 2, 2]])
row_ind, col_ind = linear_sum_assignment(cost_matrix)
print(f"Optimal assignment: {list(zip(row_ind, col_ind))}")
print("SUCCESS")
EOF
```

### Automated Verification

```bash
# Run verification script
python3 scripts/verify_scipy.py

# Expected output:
# ✓ PASS: numpy version X.X.X imported successfully
# ✓ PASS: scipy version X.X.X imported successfully
# ✓ PASS: linear_sum_assignment working correctly
# ✓ All checks passed - scipy is ready for production use
```

## Troubleshooting

### Error: "No module named 'scipy'"

**Cause**: Virtual environment not activated or scipy not installed

**Solution:**
```bash
source venv/bin/activate
python3 scripts/verify_scipy.py
```

### Error: "externally-managed-environment"

**Cause**: Attempting to install to system Python on managed systems

**Solution**: Use virtual environment (Option 1 above)

### Import Error in Services

**Cause**: Service running with wrong Python interpreter

**Solution:**
```bash
# Ensure services use venv python
venv/bin/python3 app/main.py

# Or activate venv first
source venv/bin/activate
python3 app/main.py
```

## Environment Variables

### For Development

```bash
# .env file
VIRTUAL_ENV=/home/rigade/Testing/ai-model-validation-platform/backend/venv
PATH=$VIRTUAL_ENV/bin:$PATH
```

### For Production (systemd service example)

```ini
[Service]
Environment="VIRTUAL_ENV=/opt/ai-validation/backend/venv"
Environment="PATH=/opt/ai-validation/backend/venv/bin:/usr/bin:/bin"
ExecStart=/opt/ai-validation/backend/venv/bin/python3 app/main.py
```

## Dependencies

### Required Python Packages

```txt
numpy>=1.24.0
scipy>=1.10.0
```

### Install All Backend Dependencies

```bash
source venv/bin/activate
pip3 install -r requirements.txt
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Create virtual environment
        run: python3 -m venv venv

      - name: Install dependencies
        run: |
          source venv/bin/activate
          pip install -r requirements.txt

      - name: Verify scipy
        run: |
          source venv/bin/activate
          python3 scripts/verify_scipy.py

      - name: Run tests
        run: |
          source venv/bin/activate
          pytest tests/
```

## Best Practices

1. **Always use virtual environment** for development and production
2. **Activate venv** before running any backend services
3. **Pin scipy version** in requirements.txt (e.g., `scipy==1.16.1`)
4. **Run verification script** after environment setup
5. **Document scipy requirement** in API documentation
6. **Include scipy checks** in health check endpoints
7. **Use Docker** for consistent production environments

## References

- [Scipy Documentation](https://docs.scipy.org/)
- [linear_sum_assignment](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html)
- [Python Virtual Environments](https://docs.python.org/3/library/venv.html)

## Support

For issues with scipy installation, contact the development team or create an issue in the project repository.

---

**Last Updated**: 2025-11-20
**Scipy Version**: 1.16.1
**Python Version**: 3.11+
